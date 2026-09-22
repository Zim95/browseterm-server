'''
remotetunelling.md Phase 5/7 - single-use terminal authorization tickets.

Two endpoints, two very different callers/trust levels:

- create_terminal_session: internal-token-gated, called by Local server-to-server on the
  browser's behalf (Local has already authenticated the browser's own session cookie itself -
  same trust boundary every other container-mutating route in container_handlers.py already
  uses). The browser itself never talks to Cloud directly for this: Cloud has no established way
  to authenticate a browser session directly today (Local owns that cookie), so routing through
  Local here is consistent with every other container operation rather than inventing a second,
  parallel auth path just for this one call.

- consume_terminal_session: Bearer-device-token-gated (authenticate_device, same decorator
  device_handlers.py's routes already use), called by socket-ssh itself, proving it's running on
  the same device the ticket was issued for. "Possession of the public ngrok URL is not
  authorization" (remotetunelling.md) - this is the check that actually enforces that: a ticket
  minted for device A can never be redeemed by a connection socket-ssh instance running as
  device B, even if that instance somehow received the URL.
'''
import asyncio
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from browseterm_db.models.containers import ContainerStatus
from browseterm_db.models.devices import DeviceStatus, TunnelStatus
from browseterm_db.operations.all_operations import ContainerOps, DeviceOps

from src.authentication.terminal_ticket_manager import TerminalTicketManager
from src.cloud.config import CLOUD_INTERNAL_API_TOKEN, DB_CONFIG, TUNNEL_OFFLINE_THRESHOLD_SECONDS
from src.cloud.device_handlers import authenticate_device
from src.common.logging_setup import get_logger

logger = get_logger("cloud_terminal_handlers")


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


def _unauthorized() -> JSONResponse:
    return JSONResponse(content={"error": "Unauthorized"}, status_code=401)


def _tunnel_is_online(device: dict) -> bool:
    if device.get("status") != DeviceStatus.ACTIVE.value:
        return False
    if device.get("tunnel_status") != TunnelStatus.ONLINE.value:
        return False
    last_heartbeat = device.get("tunnel_last_heartbeat_at")
    if not last_heartbeat:
        return False
    if isinstance(last_heartbeat, str):
        last_heartbeat = datetime.fromisoformat(last_heartbeat)
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()
    return age_seconds <= TUNNEL_OFFLINE_THRESHOLD_SECONDS


def _wss_url(device: dict) -> str:
    '''https://... -> wss://... - the ONLY conversion ever applied, and only ever server-side
    (remotetunelling.md: "Do not accept a WebSocket URL supplied by the browser").'''
    public_url = device["tunnel_public_url"]
    return "wss://" + public_url.removeprefix("https://")


async def create_terminal_session(request: Request) -> JSONResponse:
    '''POST /internal/containers/{container_id}/terminal-session -- body: {"user_id": "..."}.'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id: str = request.path_params["container_id"]
        body: dict = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)

        container_ops = ContainerOps(DB_CONFIG)
        container_result = await asyncio.to_thread(
            container_ops.find_one, {"id": container_id, "user_id": user_id}
        )
        container = container_result.data
        if not container:
            return JSONResponse(content={"error": "Container not found"}, status_code=404)
        if container["status"] != ContainerStatus.RUNNING.value:
            return JSONResponse(content={"error": "Container is not running"}, status_code=409)
        device_id = container.get("device_id")
        if not device_id:
            return JSONResponse(content={"error": "Container has no active device"}, status_code=409)

        device_ops = DeviceOps(DB_CONFIG)
        device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        device = device_result.data
        if not device or not _tunnel_is_online(device):
            return JSONResponse(content={"error": "Device is offline"}, status_code=409)

        ticket = TerminalTicketManager().create_ticket(
            user_id, device_id, container_id, container["placement_generation"]
        )
        expires_at = datetime.now(timezone.utc).timestamp() + 30
        logger.info(
            "terminal.ticket_issued",
            extra={"container_id": container_id, "device_id": device_id, "user_id": user_id},
        )
        return JSONResponse(content={
            "websocket_url": _wss_url(device),
            "ticket": ticket,
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        })
    except Exception:
        logger.error("terminal session creation failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating terminal session"}, status_code=500)


@authenticate_device
async def consume_terminal_session(request: Request) -> JSONResponse:
    '''POST /internal/terminal-tickets/consume -- Bearer device-token gated. Body: {"ticket": "..."}.
    Returns only what socket-ssh actually needs to attach to the authorized container - the
    client-supplied ssh_host/port/username/password path this replaces (socket-ssh/src/handler.js)
    is what let a caller pick any target it liked; this response IS the target, sourced from the
    container's own DB row, never from anything the WebSocket client said.'''
    try:
        body: dict = await request.json()
        ticket = body.get("ticket")
        if not ticket:
            return JSONResponse(content={"error": "ticket is required"}, status_code=400)

        data = TerminalTicketManager().consume_ticket(ticket)
        if not data:
            logger.warning("terminal.ticket_rejected", extra={"reason": "missing_or_expired_or_replayed"})
            return JSONResponse(content={"error": "Invalid or expired ticket"}, status_code=401)

        if data["device_id"] != request.state.device_id:
            logger.warning(
                "terminal.ticket_rejected",
                extra={"reason": "wrong_device", "ticket_device_id": data["device_id"]},
            )
            return JSONResponse(content={"error": "Invalid or expired ticket"}, status_code=401)

        container_ops = ContainerOps(DB_CONFIG)
        container_result = await asyncio.to_thread(
            container_ops.find_one, {"id": data["container_id"], "user_id": data["user_id"]}
        )
        container = container_result.data
        if not container or container["status"] != ContainerStatus.RUNNING.value:
            logger.warning("terminal.ticket_rejected", extra={"reason": "container_not_running"})
            return JSONResponse(content={"error": "Container is not available"}, status_code=409)

        # A ticket is minted against a specific placement (device + generation). If the container
        # moved (hibernate/resume onto a different device, or a new placement on the same device)
        # in the short window between issuance and redemption, the ticket must not be honored
        # against the container's new placement - stale-generation rejection, same principle every
        # other command/result path in this migration already applies.
        if (
            container.get("device_id") != data["device_id"]
            or container.get("placement_generation") != data["placement_generation"]
        ):
            logger.warning("terminal.ticket_rejected", extra={"reason": "stale_placement"})
            return JSONResponse(content={"error": "Container is not available"}, status_code=409)

        ssh_port_mapping = next(
            (p for p in (container.get("port_mappings") or []) if p.get("target_port") == 22), None
        )
        if not ssh_port_mapping:
            return JSONResponse(content={"error": "Container has no SSH port configured"}, status_code=409)
        env_vars = container.get("environment_vars") or {}

        logger.info("terminal.ticket_consumed", extra={"container_id": data["container_id"]})
        return JSONResponse(content={
            "container_id": data["container_id"],
            "ssh_host": container["ip_address"],
            "ssh_port": ssh_port_mapping["target_port"],
            "ssh_username": env_vars.get("SSH_USERNAME"),
            "ssh_password": env_vars.get("SSH_PASSWORD"),
        })
    except Exception:
        logger.error("terminal ticket consumption failed", exc_info=True)
        return JSONResponse(content={"error": "Error consuming terminal ticket"}, status_code=500)
