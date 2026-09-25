'''
Cloud browser-facing JSON API (migration Part 3).

Every route here is session-cookie-authenticated directly against Redis (src.cloud.session_auth),
never the X-Internal-Service-Token a browser could never safely hold. user_id is ALWAYS derived
from the validated session, never trusted from the request body/query string, even though the
underlying container_handlers.py functions this delegates to were originally written to trust a
caller-supplied user_id (that trust was fine when the only caller was browseterm-server-local,
itself already gated by the internal token - it is never fine for a browser). This is the
concrete fix for the "review the trust model, don't just copy it" instruction: these wrappers
exist specifically so the container_handlers.py internal-token routes never need to be exposed to
a browser directly, and so nothing here ever forwards a client-supplied user_id anywhere.

State-changing routes (create/delete/resume/hibernate a container, logout) additionally require
the double-submit CSRF header (src.cloud.session_auth.csrf_ok) - see that module's docstring.
Read-only routes (list/get containers, device quota) do not need it (matches the CSRF spec's own
scope: only state-changing requests are a forgery target).
'''
import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from browseterm_db.models.containers import ContainerStatus
from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations.all_operations import ContainerOps, DeviceOps, ImageOps

from src.cloud.config import (
    DB_CONFIG, DEVICE_COMMAND_HIBERNATE_ENABLED, DEVICE_COMMAND_SAVE_ENABLED, CLOUD_INTERNAL_API_TOKEN,
)
from src.cloud.container_handlers import (
    create_container as _internal_create_container,
    delete_container as _internal_delete_container,
    resume_container as _internal_resume_container,
    _hibernate_container_via_device_command,
    _save_container_via_device_command,
    _device_available,
)
from src.cloud.terminal_handlers import _tunnel_is_online, _wss_url
from src.authentication.terminal_ticket_manager import TerminalTicketManager
from src.authentication.session_manager import RedisSessionManager
from src.cloud.session_auth import get_json_session, csrf_ok, clear_session_cookies
from src.common.logging_setup import get_logger

logger = get_logger("browser_handlers")


def _unauthorized() -> JSONResponse:
    return JSONResponse(content={"error": "Not authenticated"}, status_code=401)


def _forbidden_csrf() -> JSONResponse:
    return JSONResponse(content={"error": "Invalid CSRF token"}, status_code=403)


class _InternalRequestShim:
    '''
    A minimal stand-in for a FastAPI Request, just enough to call
    container_handlers.py's existing internal-token-gated functions in-process (no real HTTP
    hop) while forcing the trusted user_id this module already derived from the session - never
    the raw request body's own user_id. Only the attributes those functions actually read
    (headers/json()/path_params/query_params) are provided.

    Kept deliberately separate from the real browser Request: these functions must see the
    X-Internal-Service-Token so their own `_internal_auth_ok` check passes (this module IS the
    trusted caller, exactly as browseterm-server-local used to be - the only thing that changed
    is Cloud now authenticates the browser itself first), and must see a body whose user_id can
    only ever be the one this module resolved from the real session cookie.
    '''
    def __init__(self, body: dict, path_params: dict | None = None, query_params: dict | None = None) -> None:
        self._body = body
        self.headers = {"X-Internal-Service-Token": CLOUD_INTERNAL_API_TOKEN}
        self.path_params = path_params or {}
        self.query_params = query_params or {}

    async def json(self) -> dict:
        return self._body


async def _require_session(request: Request):
    session_data = await get_json_session(request)
    if not session_data:
        return None
    return session_data.user_info.get("id")


async def logout(request: Request) -> Response:
    '''POST /app/logout - mirrors browseterm-server-local's own logout exactly (CSRF-checked,
    revokes the Redis session, clears both cookies), just applied directly instead of over HTTP.'''
    if not csrf_ok(request):
        return _forbidden_csrf()
    session_id = request.cookies.get("session")
    if session_id:
        try:
            await asyncio.to_thread(RedisSessionManager().delete_session, session_id)
        except Exception:
            logger.error("logout: session deletion failed", exc_info=True)
    response = JSONResponse(content={"message": "Logged out successfully", "success": True})
    clear_session_cookies(response)
    return response


async def auth_refresh(request: Request) -> JSONResponse:
    '''POST /app/auth/refresh - deliberately does not redirect on failure, matching
    browseterm-server-local's own auth_refresh reasoning verbatim: a 302 is wrong for an XHR/fetch
    call, the frontend needs a clean 401 to detect and navigate to /login itself.'''
    session_data = await get_json_session(request)
    if not session_data:
        return JSONResponse(content={"error": "Not authenticated"}, status_code=401)
    return JSONResponse(content={"status": "ok"}, status_code=200)


async def list_containers(request: Request) -> JSONResponse:
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    ops = ContainerOps(DB_CONFIG)
    # exclude_deleted: a container mid-DELETE is soft-deleted immediately (deleted_at stamped)
    # so it disappears from the user's list right away, while the real Kubernetes teardown - and
    # the row's eventual hard delete - continue asynchronously in the background.
    result = await asyncio.to_thread(ops.find, {"user_id": user_id}, exclude_deleted=True)
    if not result.success:
        logger.error("list containers failed", extra={"error": result.error})
        return JSONResponse(content={"error": "Error listing containers"}, status_code=500)
    return JSONResponse(content={"containers": result.data})


async def get_container(request: Request) -> JSONResponse:
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    container_id = request.path_params["container_id"]
    ops = ContainerOps(DB_CONFIG)
    result = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
    if not result.data:
        return JSONResponse(content={"error": "Container not found"}, status_code=404)
    return JSONResponse(content={"container": result.data})


async def create_container(request: Request) -> JSONResponse:
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    body = await request.json()
    # user_id is never taken from the browser-supplied body - always the session's own, even if
    # the body happens to carry a (possibly forged) user_id of its own.
    trusted_body = {**body, "user_id": user_id}
    shim = _InternalRequestShim(trusted_body)
    return await _internal_create_container(shim)


async def delete_container(request: Request) -> JSONResponse:
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    container_id = request.path_params["container_id"]
    shim = _InternalRequestShim({"user_id": user_id}, path_params={"container_id": container_id})
    return await _internal_delete_container(shim)


async def resume_container(request: Request) -> JSONResponse:
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    container_id = request.path_params["container_id"]
    shim = _InternalRequestShim({"user_id": user_id}, path_params={"container_id": container_id})
    return await _internal_resume_container(shim)


async def hibernate_container(request: Request) -> JSONResponse:
    '''
    POST /app/containers/{container_id}/hibernate - genuinely new (migration Part 3): no
    browser-reachable manual hibernate existed before this. Reuses
    _hibernate_container_via_device_command exactly as request_hibernate_command (Device Agent's
    own local-API caller) does, just ownership-scoped by the browser session instead of a device
    Bearer token. Only a RUNNING container with an assigned device can be hibernated this way -
    same preconditions request_hibernate_command already enforces.

    qa.md item 3: manual/UI hibernate must NOT save on its own - skip_save=True makes this fast
    (free the resource, delete the pod immediately); the user hits Save separately beforehand if
    they want a snapshot. Reaper's own idle-timeout hibernate (request_hibernate_command below)
    does not set this, so it still saves before deleting (qa.md item 4).
    '''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    container_id = request.path_params["container_id"]
    ops = ContainerOps(DB_CONFIG)
    existing = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
    if not existing.data:
        return JSONResponse(content={"error": "Container not found"}, status_code=404)
    if existing.data["status"] != ContainerStatus.RUNNING.value:
        return JSONResponse(content={"error": "Only a running terminal can be hibernated"}, status_code=409)
    if not existing.data.get("device_id"):
        return JSONResponse(content={"error": "Container has no assigned device"}, status_code=409)
    if not DEVICE_COMMAND_HIBERNATE_ENABLED:
        return JSONResponse(content={"error": "Hibernate is not currently enabled"}, status_code=503)
    return await _hibernate_container_via_device_command(existing.data, skip_save=True)


async def save_container(request: Request) -> JSONResponse:
    '''
    POST /app/containers/{container_id}/save - genuinely new (2026-09-22): the owner's explicit
    instruction was that Save is a core reliability feature and must work exactly like every
    other lifecycle command (durable Device Command over the control stream), not a bespoke
    synchronous path - and must not be dropped just because Cloud no longer talks to Container
    Maker directly. Mirrors hibernate_container above almost exactly; the only real difference is
    Save keeps the container RUNNING throughout, so there is no "only a running terminal can be
    saved" vs. "hibernated" distinction to draw beyond the same RUNNING precondition.
    '''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    container_id = request.path_params["container_id"]
    ops = ContainerOps(DB_CONFIG)
    existing = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
    if not existing.data:
        return JSONResponse(content={"error": "Container not found"}, status_code=404)
    if existing.data["status"] != ContainerStatus.RUNNING.value:
        return JSONResponse(content={"error": "Only a running terminal can be saved"}, status_code=409)
    if not existing.data.get("device_id"):
        return JSONResponse(content={"error": "Container has no assigned device"}, status_code=409)
    if not DEVICE_COMMAND_SAVE_ENABLED:
        return JSONResponse(content={"error": "Save is not currently enabled"}, status_code=503)
    return await _save_container_via_device_command(existing.data)


async def device_quota(request: Request) -> JSONResponse:
    '''GET /app/device-quota - this session's currently-ACTIVE device, for the terminals page's
    resource controls (mirrors browseterm-server-local's own get_device_quota, applied directly
    instead of proxying Cloud's internal active-device lookup over HTTP).'''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    device_ops = DeviceOps(DB_CONFIG)
    result = await asyncio.to_thread(device_ops.find_one, {"user_id": user_id, "status": DeviceStatus.ACTIVE})
    if not result.data:
        return JSONResponse(content={"device": None})
    device = result.data
    available_cpu, available_memory, available_storage = _device_available(device)
    return JSONResponse(content={"device": {**device, "available_cpu": available_cpu, "available_memory_bytes": available_memory, "available_storage_bytes": available_storage}})


async def terminal_session(request: Request) -> JSONResponse:
    '''
    POST /app/terminal-session - the browser's "Play/Open Terminal" click. Ownership-scoped
    lookup, then the exact same ticket-issuing logic create_terminal_session (the internal-token
    route Device Agent/Local never actually calls any more for this - this IS the replacement)
    uses, just reached directly instead of through an internal-token hop, since this module is
    already the trusted, session-authenticated caller.
    '''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)
    container_id = body.get("container_id")
    if not container_id:
        return JSONResponse(content={"error": "container_id is required"}, status_code=400)

    container_ops = ContainerOps(DB_CONFIG)
    container_result = await asyncio.to_thread(container_ops.find_one, {"id": container_id, "user_id": user_id})
    container = container_result.data
    if not container:
        return JSONResponse(content={"error": f"Container {container_id} not found"}, status_code=404)
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
    return JSONResponse(content={"websocket_url": _wss_url(device), "ticket": ticket})


async def container_activity(request: Request) -> JSONResponse:
    '''
    POST /app/containers/{container_id}/activity - terminal-page activity heartbeat. Mirrors
    browseterm-server-local's own container_activity exactly: (a) validating the session here
    already refreshes its TTL (get_json_session extends on every valid call), so terminal-only
    work never silently logs the user out, and (b) stamps last_active_at - the idle signal the
    reaper reads to decide what to hibernate. Ownership-scoped ({id, user_id} together).
    '''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    if not csrf_ok(request):
        return _forbidden_csrf()
    container_id = request.path_params["container_id"]
    ops = ContainerOps(DB_CONFIG)
    from datetime import datetime, timezone
    result = await asyncio.to_thread(
        ops.update, {"id": container_id, "user_id": user_id}, {"last_active_at": datetime.now(timezone.utc)}
    )
    if not result.success:
        logger.error("activity heartbeat failed", extra={"error": result.error, "container_id": container_id})
        return JSONResponse(content={"error": "Error recording activity"}, status_code=500)
    return JSONResponse(content={"status": "ok"})


async def list_images(request: Request) -> JSONResponse:
    '''GET /app/catalog/images - read-only, no ownership scoping (images are global).'''
    user_id = await _require_session(request)
    if not user_id:
        return _unauthorized()
    ops = ImageOps(DB_CONFIG)
    result = await asyncio.to_thread(ops.find, {"is_active": True})
    if not result.success:
        logger.error("list images failed", extra={"error": result.error})
        return JSONResponse(content={"error": "Error listing images"}, status_code=500)
    return JSONResponse(content={"images": result.data})
