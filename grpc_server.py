'''
Cloud Device Control gRPC server entrypoint (BROWSETERM_CLOUD_CONTROL_PLANE_MIGRATION.md Part 6).

Deployed as its OWN Kubernetes Deployment (`browseterm-control-grpc`, Part 20's target workload
list) separate from `app.py`'s HTTP service (`browseterm-cloud-web`). Part 6 explicitly allows a
single control-service replica for the first deployment while the web service may have multiple
replicas - this process assumes exactly that: the in-memory ConnectionRegistry
(src/control/connection_registry.py) is process-local, not shared across replicas. Do not scale
this deployment beyond 1 replica without first building the multi-replica ownership mechanism the
migration doc describes (PostgreSQL/Redis notification to the connection-owning replica, or a
dedicated dispatcher).
'''
import asyncio
import signal

from src.common.logging_setup import configure_logging
configure_logging("browseterm-control-grpc")

import grpc

from device_control_spec import device_control_pb2_grpc
from device_control_spec.device_control_pb2 import CloudToDevice
from device_control_spec.device_control_types_pb2 import ServerDraining

from src.control.config import GRPC_CONTROL_PORT, DRAIN_GRACE_SECONDS
from src.control.connection_registry import connection_registry
from src.control.command_broadcaster import command_broadcaster
from src.control.servicer import DeviceControlServicer
from src.common.logging_setup import get_logger

logger = get_logger("grpc_server")


async def _drain(server: grpc.aio.Server) -> None:
    logger.info("draining: notifying connected devices", extra={"count": len(connection_registry.all_connected_device_ids())})
    drain_by_unix_ms = 0  # best-effort notice; no hard deadline promised to the device today
    for device_id in connection_registry.all_connected_device_ids():
        state = connection_registry.get(device_id)
        if state is not None:
            state.queue.put_nowait(CloudToDevice(server_draining=ServerDraining(drain_by_unix_ms=drain_by_unix_ms)))
    await server.stop(DRAIN_GRACE_SECONDS)


async def serve() -> None:
    server = grpc.aio.server()
    device_control_pb2_grpc.add_DeviceControlServicer_to_server(DeviceControlServicer(), server)
    # TLS terminates at the Contabo ingress (Part 20) - same pattern as app.py's FastAPI service,
    # which also runs plaintext HTTP internally behind Traefik. gRPC clients outside the cluster
    # always see TLS; this bind is cluster-internal only.
    server.add_insecure_port(f"[::]:{GRPC_CONTROL_PORT}")

    command_broadcaster.start(loop=asyncio.get_running_loop())

    await server.start()
    logger.info("grpc_server.started", extra={"port": GRPC_CONTROL_PORT})

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("grpc_server.draining")
    await _drain(server)
    command_broadcaster.stop()
    logger.info("grpc_server.stopped")


if __name__ == "__main__":
    asyncio.run(serve())
