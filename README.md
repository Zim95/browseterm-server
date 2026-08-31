# browseterm-server

**Cloud control plane.** Owns the central Browseterm PostgreSQL/Redis state and exposes it to
Local (`browseterm-server-local`) exclusively through authenticated HTTPS APIs. This is the
*only* application server allowed to hold PostgreSQL/Redis credentials or talk to
`browseterm-db` directly.

## Architecture correction (P06)

Through P04/P05 this repository temporarily contained two entrypoints (`app.py` = the full
combined local+auth+container app, `cloud_app.py` = the Cloud skeleton/Device API) as migration
scaffolding. P06 corrected that into two physically separate repositories:

- **`browseterm-server`** (this repo) = Cloud control plane only. `cloud_app.py` was renamed to
  `app.py` since it's now the only entrypoint left here.
- **`browseterm-server-local`** = Local control plane (the old combined `app.py` and everything
  it served - OAuth login, container/workspace CRUD, ContainerMaker/Socket-SSH integration,
  templates). See that repo's README for its own architecture notes, including the documented
  transitional direct-DB dependencies it still carries pre-P07/P09/P12/P13.

Local has no PostgreSQL/Redis credentials for central state and reaches this repo only through
`src/cloud_client/` (defined in `browseterm-server-local`).

## P07 - Cloud-owned authentication

Cloud is now the sole Google/GitHub OAuth authority (see `~/browseterm/p07.md`, the authoritative
spec, and `p.md`'s "P07" section for the full write-up). Local no longer holds a Google/GitHub
client id/secret, does not perform token exchange, and does not touch Cloud's Redis/Postgres
directly for auth - it only talks to Cloud's HTTP API. Summary of what moved here:

- `GET /auth/{provider}/start` / `GET /auth/{provider}/callback` - the actual OAuth dance
  (`src/cloud/oauth_handlers.py`, `src/authentication/provider_oauth_service.py`). Public routes -
  anyone may initiate OAuth, they only ever authenticate as themselves.
- `POST /auth/handoff/redeem` - Local redeems the one-time code Cloud's callback minted, to pick
  up the session Cloud already created. Public but possession-gated (`src/authentication/
  handoff_manager.py`, Redis `auth:handoff:*`, single-use, 120s TTL).
- `POST /auth/device-bootstrap` (internal-token-gated, Local calls it after verifying the
  caller's browser session itself) and `POST /auth/device-bootstrap/redeem` (public,
  possession-gated) - the bridge from an authenticated browser/WebView session to a native
  per-device Bearer credential for `browseterm-desktop` (`src/authentication/
  device_token_manager.py`, Redis `auth:device:*`, one credential per device, independently
  revocable, 90-day TTL). Replaces the P06 interim `BROWSETERM_SESSION_COOKIE` mechanism.
- The Device API (`GET/POST /devices*`) is now `Authorization: Bearer <device_token>`
  authenticated instead of session-cookie authenticated (`src/cloud/device_handlers.py`'s
  `authenticate_device`). `POST /devices` (registration) is no longer an independently reachable
  route - it only happens inside `device-bootstrap/redeem`, since no device has a token yet at
  registration time.
- `TrustedHostMiddleware` (`BROWSETERM_ALLOWED_HOSTS`, dev-permissive `*` default). No CORS -
  browser JS never calls Cloud directly, only top-level redirects and server-to-server calls
  reach it, so it isn't needed (documented decision, not an oversight).

The pre-existing session API (`POST /auth/sessions*`, internal-token-gated) is unchanged -
Cloud's own OAuth callback calls `process_user_info` directly (in-process), same as before.

## P09/P11 - internal system APIs

Two more trusted-caller (not end-user) routes, both grown from the same "authenticate workloads
as a trusted service, never by forcing a user-scoped credential onto them" principle P07
established:

- `POST /internal/containers/{container_id}/status` (P09, `src/cloud/container_handlers.py`) -
  `browseterm_workload`'s `status_monitor` calls this instead of writing to Postgres directly. No
  `user_id` - `status_monitor` watches every user's pods cluster-wide, it isn't acting for any one
  user's request. Internal-token-gated. Supports an optional `expected_status` for an atomic
  conditional update (compare-and-swap), reproducing the old direct-DB `mark_lost_if_running`'s
  exact semantics.
- `POST /auth/websocket-tokens/consume` (P11, `src/cloud/auth_handlers.py`) - `socket-ssh` calls
  this instead of reading/deleting `ws_token:*` from Redis directly. **Public but
  possession-gated** (no internal token, unlike everything else in this section) - holding a
  valid one-time token is itself the authorization, the same pattern P07's handoff/device-
  bootstrap redemption already established. Atomically consumes the token (`GETDEL`) and verifies
  the linked session is still valid.

## P10 - Cloud owns LISTEN/NOTIFY and SSE

Cloud now pushes real-time container status/save-status updates directly to the browser -
`browseterm-server-local` no longer polls Cloud's `GET /containers` on an interval and relays it
through its own SSE endpoint (that whole mechanism is removed as of this task; see that repo's
README for the Local-side half of this change).

- `src/cloud/sse_broadcaster.py` - a singleton that starts `browseterm_db.common.pg_listener.
  PGListener` (a pre-existing thread-based `psycopg2` LISTEN client) in a background thread on app
  startup (new FastAPI `lifespan` in `app.py`), and bridges its NOTIFY callbacks into the asyncio
  event loop via `call_soon_threadsafe` to fan them out to per-user `asyncio.Queue` subscribers.
  The actual `container_status_change`/`container_save_status_change` Postgres triggers this
  listens for already existed in `browseterm-db`'s migration history - they'd just never been
  applied to this project's dev cluster (see `~/browseterm/p.md`'s P10 section for the full story
  of how that gap was found and fixed).
- `GET /events/stream?token=<sse_token>` (`src/cloud/sse_handlers.py`) - the browser connects here
  directly. **Public but possession-gated**, same pattern as P11's ws-token-consume: the token is
  in the query string (`EventSource` can't set custom headers) and resolves only to a session_id;
  the subscribing user_id is read from that session's own server-side data, never trusted from
  the request itself.
- `POST /auth/sse-tokens` (`src/cloud/auth_handlers.py`) - internal-token-gated, mints the token
  above. Unlike `POST /auth/websocket-tokens`, **not single-use** - `EventSource` reconnects
  automatically using the same URL after any drop, so a `GETDEL` token would break the very first
  automatic reconnect.

## P12 - workspace creation validates the device and reserves resources

`POST /containers` requires `cpu_limit`/`memory_limit`/`storage_limit` and, before creating the
row: looks up the device (rejects if not found or not `ACTIVE`), validates the request against
`allocated - used` for cpu/memory/storage, and reserves usage (increments the device's `used_*`
fields) - released back if the row insert then fails. `device_id` is optional as of P13 below.
`POST /containers/{id}/delete` releases a container's reserved resources back to its device on
success. `src/cloud/resource_quantity.py` is a small dependency-free parser for the Kubernetes
resource-quantity strings (`"500m"`, `"2Gi"`) these fields are stored as - Cloud doesn't depend on
the `kubernetes` client library (P06 moved that to `browseterm-server-local`), so
`kubernetes.utils.quantity.parse_quantity` isn't reachable from here. See `~/browseterm/p.md`'s
P12 section for the full write-up, including why Hibernate/Resume accounting isn't wired up yet.

## P13 - device_id auto-resolves to the caller's active device

`browseterm-server-local` (a per-user-Mac process) has no established way to learn "its own"
device_id - device registration/bootstrap (P07) is a `browseterm-desktop`-only concept, a separate
process Local has no IPC channel to. So `POST /containers`'s `device_id` is optional: when
omitted, Cloud resolves the caller's currently-`ACTIVE` device automatically (reusing the "at most
one ACTIVE device per user" invariant `device_handlers.py` already enforces elsewhere), or returns
`400` if the user has no active device at all. See `~/browseterm/p.md`'s P13 section.

## P14 - resource reconciliation

`POST /internal/devices/resources/reconcile` (`src/cloud/container_handlers.py`) - `status_monitor`
(`browseterm_workload`) periodically reports the container_ids of pods it currently sees actually
`Running` in real Kubernetes. For each one, its container row is looked up (no `user_id` filter -
same trusted-SYSTEM-caller pattern as `update_container_status`), grouped by `device_id`, and each
implicated device's `used_cpu`/`used_memory_bytes`/`used_storage_bytes` is **overwritten** to the
freshly-computed sum - a repair, not an adjustment, closing the loop on drift P12's reservation
counters can accumulate. Known v1 limitation: a device whose containers have *all* stopped running
since the last reconcile isn't reset to zero by this alone, since nothing in the request
identifies it as needing reconciliation - see `~/browseterm/p.md`'s P14 section for why this is a
deliberate scope decision.

## P16 - snapshot version allocation

`POST /internal/containers/{container_id}/snapshots/allocate` (`src/cloud/snapshot_handlers.py`)
- `snapshot_job` (`browseterm_workload`) uses this to allocate a `container_snapshots` row (P15)
  for a save attempt. Same trusted-SYSTEM-caller pattern as P09/P14. Reuses an existing
  `(container_id, request_id)` row verbatim if one exists (idempotent retry), else reads/
  increments `containers.next_snapshot_sequence` (a plain increment - the plan explicitly
  tolerates version-number gaps after crashes) and creates a new `Pending` row.
  `SNAPSHOT_REGISTRY_REPO_PREFIX` builds the flat, UUID-based `image_repository`. See
  `~/browseterm/p.md`'s P16 section.

## P17 - snapshot job reports results through Cloud

`POST /internal/containers/{container_id}/snapshots/{snapshot_id}/report`
(`src/cloud/snapshot_handlers.py`) - `snapshot_job` calls this as it progresses through a save
attempt (`Running` -> `Succeeded`/`Failed`, with the registry digest on success) instead of
writing to Postgres directly. Updates BOTH the `container_snapshots` row itself and the owning
`containers` row's `save_status`/`save_error` (the frontend's SSE feed is driven by `containers`'
own NOTIFY trigger, not `container_snapshots`). `saved_image`/`last_saved_at` on `containers` are
only ever set when `status == "Succeeded"` - plan section 13: "On failure, saved_image must
remain unchanged." See `~/browseterm/p.md`'s P17 section.

## P18 - reaper's idle-scan and hibernate through Cloud

`GET /internal/devices/{device_id}/containers/idle?idle_threshold_seconds=N` and
`POST /internal/containers/{container_id}/hibernate` (`src/cloud/container_handlers.py`) -
`reaper` (`browseterm_workload`) uses these instead of a direct Postgres connection. The idle
list is scoped to a single `device_id` - "the reaper must operate only on containers whose
device_id is the current device" (plan section 16). Hibernate is the compound transition plan
section 14 describes: `status=HIBERNATED`, `device_id=NULL`, and the container's device resource
reservation released (reusing the same `_release_device_resources` helper `delete_container`
uses) - reaper only calls this after it has itself confirmed the save this hibernate is based on
actually succeeded; this endpoint has no save-confirmation logic of its own. See
`~/browseterm/p.md`'s P18 section.

## What's here

- `app.py` - FastAPI entrypoint: `GET /healthz`, OAuth (above), the Device Cloud API
  (`GET /devices`, `GET/POST /devices/{device_id}`, `POST /devices/{device_id}/heartbeat`).
- `src/cloud/` - Cloud-only route handlers/config.
- `src/authentication/` - `session_manager.py`/`authentication_helpers.py` (the
  `authenticate_session` Redis-session decorator, still used by the internal-token-gated session
  API), `oauth_state_manager.py`/`handoff_manager.py`/`device_token_manager.py`/
  `provider_oauth_service.py` (P07, see above).
- `src/db_ops/user_db_ops.py`, `subscription_db_ops.py` - the DB operations
  `authenticate_session`/`process_user_info` need transitively (user/subscription lookups).
  Legitimate direct Postgres access - Cloud owns `users`/`subscriptions` per the plan.
- `infra/cloud/`, `scripts/cloud/` - Kubernetes Deployment/Service/Ingress and build/setup/
  teardown scripts for this Cloud process. The Ingress is new in P07 - before this, nothing
  outside the cluster needed to reach Cloud; now the browser hits `/auth/*` directly.

## Dev setup

```
poetry env use python3.11   # repo pins python >=3.11,<3.12
poetry install
```

Create an `env.mk` (see `browseterm-monorepo/env.mk.example`) with `NAMESPACE`, `REPO_NAME`,
`USER_NAME`, `REDIS_*`, `POSTGRES_HOST`/`POSTGRES_PORT` (user/password/db come from the
`browseterm-db-credentials` Secret in-cluster, not `env.mk`), `AUTH_REDIRECT_BASE_URI` (Cloud's
own public base URL, e.g. `http://browseterm.cloud.com:9999`), `BROWSETERM_LOCAL_CALLBACK_URL`
(Local's `/auth/callback`, e.g. `http://browseterm.local.com/auth/callback`),
`BROWSETERM_ALLOWED_HOSTS`, `CLOUD_INGRESS_HOST`, plus a `browseterm-oauth-credentials` Secret
in-cluster with `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GITHUB_CLIENT_ID`/
`GITHUB_CLIENT_SECRET` (never in `env.mk` - these are real provider secrets), then:

```
make build      # ./scripts/cloud/cloud-build.sh
make setup      # ./scripts/cloud/cloud-setup.sh
make teardown   # ./scripts/cloud/cloud-teardown.sh
```

**Your OAuth app's authorized redirect URIs must include** `${AUTH_REDIRECT_BASE_URI}/auth/google/callback`
and `${AUTH_REDIRECT_BASE_URI}/auth/github/callback` (Google Cloud Console / GitHub OAuth App
settings) - Google/GitHub reject the callback otherwise (`redirect_uri_mismatch`).

Running locally without Kubernetes: `poetry run uvicorn app:app --host 0.0.0.0 --port 9999`
(needs `REDIS_*`/`POSTGRES_*`/OAuth env vars above - no kubeconfig, ContainerMaker, Socket-SSH, or
payment-gateway connectivity required to start).

### Local dev cluster note (k3d)

If your cluster is `k3d` (not Docker Desktop's built-in Kubernetes or a Multipass VM - check
`kubectl config current-context`), **disable k3s's bundled Traefik** before installing
ingress-nginx, or its `svclb` will squat on host ports 80/443 and ingress-nginx's own `svclb`
will sit `Pending` forever: `kubectl -n kube-system delete helmchart traefik` (on an already-
running cluster), or pass `--k3s-arg '--disable=traefik@server:*'` at `k3d cluster create` time.
Build images locally and `k3d image import <image> -c <cluster-name>` instead of pushing to a
registry - much faster for local dev, no registry credentials needed.

## Working with dependencies

- Add: `poetry add <dependency>`
- Add with a specific version: edit `pyproject.toml`, then `poetry update`
- Remove: `poetry remove <dependency>`

## Running tests

```
poetry install
poetry run python -m pytest tests/ -v
```

Most tests live under `tests/integration/cloud/` (route-handler level, boundaries mocked -
`test_oauth_handlers.py` is the P07 OAuth/handoff/device-bootstrap suite, `test_device_api.py`
covers the Bearer-token-scoped Device API). `tests/unit/authentication/test_auth_managers.py`
exercises `OAuthStateManager`/`HandoffManager`/`DeviceTokenManager` directly against an in-memory
Redis stand-in (GETDEL single-use semantics, wrong-purpose/wrong-provider rejection, token
hashing). `test_cloud_startup_independence.py` is the load-bearing one for the Cloud-only
boundary: it proves `app.py` imports cleanly with no reachable kubeconfig and that its import
graph never reaches `kubernetes`, ContainerMaker's or the payment-gateway's service modules, or
`src.api_handlers` - all of which no longer exist in this repository at all as of P06 (they moved
to `browseterm-server-local`).
