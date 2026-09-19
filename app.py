'''
Cloud browseterm-server entrypoint.

As of P06, this repository (browseterm-server) IS the Cloud control plane, full stop - not one
of two entrypoints sharing a repo with Local code. The former local browser-facing server (the
old combined `app.py`, everything reachable through `src.api_handlers` ->
`src.containers.containers_service` / `src.payments.payments_service` -> `src.common.k8s_secrets`
- which eagerly loads a Kubernetes client config at import time) now lives entirely in the
separate `browseterm-server-local` repository. See README.md's "Architecture correction (P06)"
section for the full split rationale and boundary.

This module was `cloud_app.py` through P04/P05; renamed to `app.py` in P06 now that there is
only one entrypoint left in this repo to name.
'''
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.common.logging_setup import configure_logging
configure_logging("browseterm-server-cloud")  # structured JSON logs to stdout (before anything logs)

from src.common.config import BROWSETERM_ALLOWED_HOSTS, BROWSETERM_CORS_ALLOWED_ORIGINS

from src.cloud.health_handlers import healthz
from src.cloud.device_handlers import (
    get_active_device_internal,
    get_device,
    heartbeat_device,
    heartbeat_tunnel,
    list_devices,
    register_tunnel,
    update_device,
)
from src.cloud.auth_handlers import (
    consume_websocket_token,
    create_session_from_user_info,
    create_sse_token,
    create_websocket_token,
    delete_session,
    validate_session,
)
from src.cloud.oauth_handlers import (
    device_auth_poll,
    device_auth_start,
    device_bootstrap_redeem,
    device_bootstrap_start,
    handoff_redeem,
    oauth_callback,
    oauth_start,
)
from src.cloud.container_handlers import (
    create_container,
    delete_container,
    get_container,
    get_container_internal,
    hibernate_container,
    list_containers,
    list_active_containers_for_device,
    list_idle_containers,
    list_images,
    list_stuck_saves,
    list_subscription_types,
    reconcile_device_resources,
    resume_container,
    update_container,
    update_container_internal,
    update_container_status,
)
from src.cloud.snapshot_handlers import allocate_snapshot, report_snapshot_result
from src.cloud.sse_broadcaster import sse_broadcaster
from src.cloud.sse_handlers import events_stream
from src.cloud.terminal_handlers import consume_terminal_session, create_terminal_session
from src.cloud.subscription_handlers import get_current_subscription


@asynccontextmanager
async def lifespan(app: FastAPI):
    # P10 - starts the Postgres LISTEN background thread (src/cloud/sse_broadcaster.py) on the
    # running event loop, so its thread-safe callbacks can hand messages back to asyncio.Queue
    # subscribers. Stopped on shutdown so the LISTEN connection doesn't leak.
    sse_broadcaster.start(loop=asyncio.get_event_loop())
    yield
    sse_broadcaster.stop()


app = FastAPI(lifespan=lifespan)

# p07.md section 28 - validates the HTTP Host header only (not an authentication mechanism).
# "*" is the explicit dev-permissive default; set BROWSETERM_ALLOWED_HOSTS in production.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=BROWSETERM_ALLOWED_HOSTS)

# P10 follow-up (see src/common/config.py's BROWSETERM_CORS_ALLOWED_ORIGINS comment for the full
# story): terminals.js/terminalpage.js's EventSource connects to GET /events/stream directly from
# the browser, a genuine cross-origin request browseterm.local.com -> browseterm.cloud.com:9999.
# Deliberately scoped, not wildcard: allow_origins defaults to the one real caller (derived from
# BROWSETERM_LOCAL_CALLBACK_URL), allow_credentials=False since this endpoint is query-token
# authenticated rather than cookie-authenticated, allow_methods is just GET (EventSource never
# sends anything else), and allow_headers is left at CORSMiddleware's own default (the CORS
# safelisted headers) rather than "*", since EventSource sends no custom headers here at all -
# nothing about this needs to be any broader than what's actually used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=BROWSETERM_CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
)

app.add_api_route(path="/healthz", endpoint=healthz, methods=["GET"])

# Device Cloud API (P05, device-token auth as of P07 - see device_handlers.py). POST /devices
# (registration) is intentionally NOT a standalone route any more - see oauth_handlers.py
# device_bootstrap_redeem, the only path that can mint a new device + its token together.
app.add_api_route(path="/devices", endpoint=list_devices, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=get_device, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=update_device, methods=["POST"])
app.add_api_route(path="/devices/{device_id}/heartbeat", endpoint=heartbeat_device, methods=["POST"])
# remotetunelling.md Phase 3/4 - tunnel registration/heartbeat, same Bearer-device-token auth as
# every other /devices/{device_id}/* route above.
app.add_api_route(path="/devices/{device_id}/tunnel", endpoint=register_tunnel, methods=["POST"])
app.add_api_route(
    path="/devices/{device_id}/tunnel/heartbeat", endpoint=heartbeat_tunnel, methods=["POST"]
)
app.add_api_route(
    path="/internal/users/{user_id}/active-device", endpoint=get_active_device_internal, methods=["GET"]
)

# Session/auth API (replaces Local's direct Redis/Postgres session access) - internal-service auth
app.add_api_route(path="/auth/sessions", endpoint=create_session_from_user_info, methods=["POST"])
app.add_api_route(path="/auth/sessions/validate", endpoint=validate_session, methods=["POST"])
app.add_api_route(path="/auth/sessions/delete", endpoint=delete_session, methods=["POST"])
app.add_api_route(path="/auth/websocket-tokens", endpoint=create_websocket_token, methods=["POST"])
app.add_api_route(path="/auth/websocket-tokens/consume", endpoint=consume_websocket_token, methods=["POST"])
app.add_api_route(path="/auth/sse-tokens", endpoint=create_sse_token, methods=["POST"])

# OAuth (P07) - Cloud is the sole OAuth authority. Start/callback/handoff-redeem are public;
# device-bootstrap start is internal-token-gated, device-bootstrap redeem is public but
# possession-gated. See src/cloud/oauth_handlers.py and p07.md.
app.add_api_route(path="/auth/{provider}/start", endpoint=oauth_start, methods=["GET"])
app.add_api_route(path="/auth/{provider}/callback", endpoint=oauth_callback, methods=["GET"])
app.add_api_route(path="/auth/handoff/redeem", endpoint=handoff_redeem, methods=["POST"])
app.add_api_route(path="/auth/device-bootstrap", endpoint=device_bootstrap_start, methods=["POST"])
app.add_api_route(path="/auth/device-bootstrap/redeem", endpoint=device_bootstrap_redeem, methods=["POST"])

# OAuth Device Authorization Grant (RFC 8628) - Desktop's login flow, no Local involvement (see
# the device-auth follow-up to p07.md and src/cloud/oauth_handlers.py's route-map docstring).
# Both public; /poll is possession-gated on a live device_code from /start.
app.add_api_route(path="/auth/device/start", endpoint=device_auth_start, methods=["POST"])
app.add_api_route(path="/auth/device/poll", endpoint=device_auth_poll, methods=["POST"])

# Container/workspace metadata API (replaces Local's direct ContainerOps/ImageOps/
# SubscriptionTypeOps access)
app.add_api_route(path="/containers", endpoint=create_container, methods=["POST"])
app.add_api_route(path="/containers", endpoint=list_containers, methods=["GET"])
app.add_api_route(path="/containers/{container_id}", endpoint=get_container, methods=["GET"])
app.add_api_route(path="/containers/{container_id}", endpoint=update_container, methods=["POST"])
app.add_api_route(path="/containers/{container_id}/delete", endpoint=delete_container, methods=["POST"])
# P19 - cross-device resume: validates/reserves the resuming device's capacity and atomically
# (CAS on expected_status=HIBERNATED) transitions device_id/status. See resume_container's
# docstring for the full design.
app.add_api_route(path="/containers/{container_id}/resume", endpoint=resume_container, methods=["POST"])

# Internal system API (P09) - trusted cluster-wide callers (status_monitor) with no user_id of
# their own, unlike the user-scoped /containers/* routes above. Same internal-token auth.
app.add_api_route(
    path="/internal/containers/{container_id}/status", endpoint=update_container_status, methods=["POST"]
)
# P14 - status_monitor periodically reports its currently-Running container_ids here to repair
# any drift in P12's cached device used_* counters.
app.add_api_route(
    path="/internal/devices/resources/reconcile", endpoint=reconcile_device_resources, methods=["POST"]
)
# Durability-in-terminals: status_monitor's own periodic safety net for "the DB thinks this
# device's container is Running but I can't actually find its pod" - see the handler's own
# docstring for why this needs to be a device-scoped pull rather than relying on a live watch event.
app.add_api_route(
    path="/internal/devices/{device_id}/active-containers",
    endpoint=list_active_containers_for_device, methods=["GET"],
)
# P16 - snapshot_job allocates a container_snapshots row here instead of writing to Postgres
# directly. Same trusted-SYSTEM-caller pattern as the two routes above.
app.add_api_route(
    path="/internal/containers/{container_id}/snapshots/allocate", endpoint=allocate_snapshot, methods=["POST"]
)
# P17 - snapshot_job reports Running/Succeeded/Failed here as it progresses through a save
# attempt, instead of writing to Postgres directly.
app.add_api_route(
    path="/internal/containers/{container_id}/snapshots/{snapshot_id}/report",
    endpoint=report_snapshot_result, methods=["POST"],
)
# P18 - reaper finds its own device's idle containers and performs the hibernate transition
# through these instead of a direct Postgres connection.
app.add_api_route(
    path="/internal/devices/{device_id}/containers/idle", endpoint=list_idle_containers, methods=["GET"]
)
app.add_api_route(
    path="/internal/containers/{container_id}/hibernate", endpoint=hibernate_container, methods=["POST"]
)
# container-maker's off-direct-Postgres migration (see p.md's writeup): self-heal of a drifted
# kubernetes_id, and the save reconciler's stuck-save sweep/mark-failed. The literal
# /stuck-saves route MUST be registered before the {container_id} routes below it, or Starlette
# would match "stuck-saves" as a container_id value instead.
app.add_api_route(path="/internal/containers/stuck-saves", endpoint=list_stuck_saves, methods=["GET"])
app.add_api_route(path="/internal/containers/{container_id}", endpoint=get_container_internal, methods=["GET"])
app.add_api_route(path="/internal/containers/{container_id}", endpoint=update_container_internal, methods=["POST"])
# remotetunelling.md Phase 5/7 - single-use terminal authorization tickets. create_terminal_session
# is internal-token-gated (Local calls it server-to-server, same trust boundary as every other
# route above); consume_terminal_session is Bearer-device-token-gated (socket-ssh calls it,
# proving it's running on the ticket's own device) - see terminal_handlers.py's own docstring.
app.add_api_route(
    path="/internal/containers/{container_id}/terminal-session",
    endpoint=create_terminal_session, methods=["POST"],
)
app.add_api_route(
    path="/internal/terminal-tickets/consume", endpoint=consume_terminal_session, methods=["POST"],
)
app.add_api_route(path="/catalog/images", endpoint=list_images, methods=["GET"])
app.add_api_route(path="/catalog/subscription-types", endpoint=list_subscription_types, methods=["GET"])
app.add_api_route(path="/subscriptions/current", endpoint=get_current_subscription, methods=["GET"])

# P10 - the browser connects here directly for real-time status updates (see sse_handlers.py).
# Public but possession-gated by the sse_token query param, same trust pattern as P11's
# websocket-tokens/consume.
app.add_api_route(path="/events/stream", endpoint=events_stream, methods=["GET"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
