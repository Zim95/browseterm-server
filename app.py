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
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.common.logging_setup import configure_logging
configure_logging("browseterm-server-cloud")  # structured JSON logs to stdout (before anything logs)

from src.common.config import BROWSETERM_ALLOWED_HOSTS

from src.cloud.health_handlers import healthz
from src.cloud.device_handlers import (
    get_device,
    heartbeat_device,
    list_devices,
    update_device,
)
from src.cloud.auth_handlers import (
    create_session_from_user_info,
    create_websocket_token,
    delete_session,
    validate_session,
)
from src.cloud.oauth_handlers import (
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
    list_containers,
    list_images,
    list_subscription_types,
    update_container,
)
from src.cloud.subscription_handlers import get_current_subscription

app = FastAPI()

# p07.md section 28 - validates the HTTP Host header only (not an authentication mechanism).
# "*" is the explicit dev-permissive default; set BROWSETERM_ALLOWED_HOSTS in production.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=BROWSETERM_ALLOWED_HOSTS)

app.add_api_route(path="/healthz", endpoint=healthz, methods=["GET"])

# Device Cloud API (P05, device-token auth as of P07 - see device_handlers.py). POST /devices
# (registration) is intentionally NOT a standalone route any more - see oauth_handlers.py
# device_bootstrap_redeem, the only path that can mint a new device + its token together.
app.add_api_route(path="/devices", endpoint=list_devices, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=get_device, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=update_device, methods=["POST"])
app.add_api_route(path="/devices/{device_id}/heartbeat", endpoint=heartbeat_device, methods=["POST"])

# Session/auth API (replaces Local's direct Redis/Postgres session access) - internal-service auth
app.add_api_route(path="/auth/sessions", endpoint=create_session_from_user_info, methods=["POST"])
app.add_api_route(path="/auth/sessions/validate", endpoint=validate_session, methods=["POST"])
app.add_api_route(path="/auth/sessions/delete", endpoint=delete_session, methods=["POST"])
app.add_api_route(path="/auth/websocket-tokens", endpoint=create_websocket_token, methods=["POST"])

# OAuth (P07) - Cloud is the sole OAuth authority. Start/callback/handoff-redeem are public;
# device-bootstrap start is internal-token-gated, device-bootstrap redeem is public but
# possession-gated. See src/cloud/oauth_handlers.py and p07.md.
app.add_api_route(path="/auth/{provider}/start", endpoint=oauth_start, methods=["GET"])
app.add_api_route(path="/auth/{provider}/callback", endpoint=oauth_callback, methods=["GET"])
app.add_api_route(path="/auth/handoff/redeem", endpoint=handoff_redeem, methods=["POST"])
app.add_api_route(path="/auth/device-bootstrap", endpoint=device_bootstrap_start, methods=["POST"])
app.add_api_route(path="/auth/device-bootstrap/redeem", endpoint=device_bootstrap_redeem, methods=["POST"])

# Container/workspace metadata API (replaces Local's direct ContainerOps/ImageOps/
# SubscriptionTypeOps access)
app.add_api_route(path="/containers", endpoint=create_container, methods=["POST"])
app.add_api_route(path="/containers", endpoint=list_containers, methods=["GET"])
app.add_api_route(path="/containers/{container_id}", endpoint=get_container, methods=["GET"])
app.add_api_route(path="/containers/{container_id}", endpoint=update_container, methods=["POST"])
app.add_api_route(path="/containers/{container_id}/delete", endpoint=delete_container, methods=["POST"])
app.add_api_route(path="/catalog/images", endpoint=list_images, methods=["GET"])
app.add_api_route(path="/catalog/subscription-types", endpoint=list_subscription_types, methods=["GET"])
app.add_api_route(path="/subscriptions/current", endpoint=get_current_subscription, methods=["GET"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
