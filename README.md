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

## What's here

- `app.py` - FastAPI entrypoint: `GET /healthz`, the Device Cloud API (`POST/GET /devices`,
  `GET/POST /devices/{device_id}`, `POST /devices/{device_id}/heartbeat`).
- `src/cloud/` - Cloud-only route handlers/config.
- `src/authentication/session_manager.py` + `authentication_helpers.py` - the shared
  `authenticate_session` Redis-session decorator the Device API uses. This repo needs Redis for
  the same reason it needs Postgres: OAuth/session *issuance* is still Local's job until P07,
  but Cloud already validates sessions for its own APIs (P05's authentication-boundary
  decision - Cloud and Local currently point at the same Redis instance).
- `src/db_ops/user_db_ops.py`, `subscription_db_ops.py` - the DB operations that
  `authenticate_session` needs transitively (user/subscription lookups). Legitimate direct
  Postgres access - Cloud owns `users`/`subscriptions` per the plan, this is not migration debt.
- `infra/cloud/`, `scripts/cloud/` - Kubernetes Deployment/Service and build/setup/teardown
  scripts for this Cloud process.

## Dev setup

```
poetry env use python3.11   # repo pins python >=3.11,<3.12
poetry install
```

Create an `env.mk` (see `browseterm-monorepo/env.mk.example`) with `NAMESPACE`, `REPO_NAME`,
`USER_NAME`, `REDIS_*`, `POSTGRES_HOST`/`POSTGRES_PORT` (user/password/db come from the
`browseterm-db-credentials` Secret in-cluster, not `env.mk`), then:

```
make build      # ./scripts/cloud/cloud-build.sh
make setup      # ./scripts/cloud/cloud-setup.sh
make teardown   # ./scripts/cloud/cloud-teardown.sh
```

Running locally without Kubernetes: `poetry run uvicorn app:app --host 0.0.0.0 --port 9999`
(only needs `REDIS_*`/`POSTGRES_*` env vars - no kubeconfig, ContainerMaker, Socket-SSH, or
payment-gateway connectivity required to start).

## Working with dependencies

- Add: `poetry add <dependency>`
- Add with a specific version: edit `pyproject.toml`, then `poetry update`
- Remove: `poetry remove <dependency>`

## Running tests

```
poetry install
poetry run python -m pytest tests/ -v
```

All tests live under `tests/integration/cloud/`. `test_cloud_startup_independence.py` is the
load-bearing one for the Cloud-only boundary: it proves `app.py` imports cleanly with no
reachable kubeconfig and that its import graph never reaches `kubernetes`, ContainerMaker's or
the payment-gateway's service modules, or `src.api_handlers` - all of which no longer exist in
this repository at all as of P06 (they moved to `browseterm-server-local`).
