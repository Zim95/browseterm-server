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

from src.common.logging_setup import configure_logging
configure_logging("browseterm-server-cloud")  # structured JSON logs to stdout (before anything logs)

from src.cloud.health_handlers import healthz
from src.cloud.device_handlers import (
    get_device,
    heartbeat_device,
    list_devices,
    register_device,
    update_device,
)

app = FastAPI()

app.add_api_route(path="/healthz", endpoint=healthz, methods=["GET"])

# Device Cloud API (P05)
app.add_api_route(path="/devices", endpoint=register_device, methods=["POST"])
app.add_api_route(path="/devices", endpoint=list_devices, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=get_device, methods=["GET"])
app.add_api_route(path="/devices/{device_id}", endpoint=update_device, methods=["POST"])
app.add_api_route(path="/devices/{device_id}/heartbeat", endpoint=heartbeat_device, methods=["POST"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)
