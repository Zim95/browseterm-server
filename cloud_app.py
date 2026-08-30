'''
Cloud browseterm-server entrypoint (P04 skeleton).

This is the minimal, independently deployable Cloud control-plane app. It boots without any of
the local-only runtime dependencies (ContainerMaker, Socket-SSH, local Kubernetes workspace
cluster, MinIO) that `app.py` (today's single combined app) pulls in transitively through
`src.api_handlers` -> `src.containers.containers_service` / `src.payments.payments_service` ->
`src.common.k8s_secrets` (which eagerly loads a Kubernetes client config at import time).

`app.py` is left untouched and continues to serve everything it does today; P08 is responsible
for the eventual Local/Cloud server split. P04 only establishes that a Cloud-only process can
start, load Cloud configuration (`src/cloud/config.py`), and expose a health endpoint.

P05 adds the Device Cloud API (`src.cloud.device_handlers`) as the first such routes. P06+ add
container/workspace metadata APIs the same way.
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
