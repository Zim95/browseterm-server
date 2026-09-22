'''
Cloud browser-facing page routes (migration Part 3).

Renders the templates moved over from browseterm-server-local, adapted for Cloud's own direct
session authentication (src.cloud.session_auth) instead of Local's HTTP-hop-to-Cloud version.
Every page here reads Postgres directly (ContainerOps/DeviceOps/ImageOps) rather than going
through the internal-token-gated HTTP routes those same tables are exposed through elsewhere in
this repo - this module IS Cloud, there is no network boundary to cross to read its own database,
exactly the same reasoning every other handler in src/cloud already uses.
'''
import asyncio

from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations.all_operations import ContainerOps, DeviceOps, ImageOps

from src.authentication.session_manager import RedisSessionManager
from src.cloud.config import DB_CONFIG
from src.cloud.container_handlers import _device_available
from src.cloud.session_auth import require_page_session, get_session_data
from src.common.logging_setup import get_logger

logger = get_logger("page_handlers")

templates = Jinja2Templates(directory="templates")


async def _get_active_device(user_id: str) -> dict | None:
    device_ops = DeviceOps(DB_CONFIG)
    result = await asyncio.to_thread(device_ops.find_one, {"user_id": user_id, "status": DeviceStatus.ACTIVE})
    if not result.data:
        return None
    device = result.data
    available_cpu, available_memory, available_storage = _device_available(device)
    return {
        **device,
        "available_cpu": available_cpu,
        "available_memory_bytes": available_memory,
        "available_storage_bytes": available_storage,
    }


async def index(request: Request) -> HTMLResponse:
    '''GET / - authenticated users go to /terminals, everyone else to /login. Not decorated with
    @require_page_session on purpose: that decorator's own 302-to-/login IS what an unauthenticated
    visitor here should see, so a plain session check with a two-way redirect is clearer than
    layering the decorator and then redirecting again on success.'''
    session_data = await get_session_data(request)
    if session_data:
        return RedirectResponse(url="/terminals", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


async def login(request: Request) -> HTMLResponse:
    '''GET /login - public. Already-authenticated visitors are sent on to /terminals rather than
    shown a login page they'd immediately click away from.'''
    session_data = await get_session_data(request)
    if session_data:
        return RedirectResponse(url="/terminals", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@require_page_session
async def terminals(request: Request) -> HTMLResponse:
    '''GET /terminals - CPU/memory/storage controls are bounded by the active device's remaining
    quota, matching browseterm-server-local/src/template_handlers.py:terminals exactly. No SSE
    token dance needed here any more - the browser IS the same origin GET /events/stream lives on
    now, so it authenticates that connection with the ambient session cookie directly (see
    templates/static/js/terminals.js), not a separate query-string token minted at render time.'''
    image_ops = ImageOps(DB_CONFIG)
    images_result = await asyncio.to_thread(image_ops.find, {"is_active": True})
    images = images_result.data if images_result.success else []
    active_device = await _get_active_device(request.state.user_info["id"])
    # Same-origin now (Part 3), so this could ride the ambient session cookie directly, but
    # /events/stream's existing possession-gated sse_token mechanism (src/cloud/sse_handlers.py)
    # is already built, tested, and unchanged by this migration part - reused as-is here, just
    # minted directly against Redis instead of via an HTTP round trip to itself.
    sse_token = await asyncio.to_thread(RedisSessionManager().create_sse_token, request.state.session_id)
    return templates.TemplateResponse(
        "terminals.html",
        {
            "request": request,
            "images": images,
            "userInfo": request.state.user_info,
            "activeDevice": active_device,
            "sseToken": sse_token,
        },
    )


@require_page_session
async def terminal_page(request: Request) -> HTMLResponse:
    '''GET /terminal/{container_id} - migration Part 3's own canonical path (path param, not
    Local's old ?id= query string - templates/static/js/terminals.js's Play button link was
    updated to match).'''
    terminal_id = request.path_params.get("container_id", "")
    user_id = request.state.user_info["id"]
    if not terminal_id:
        terminal_info = {"id": "", "name": "Error", "ipAddress": "N/A", "port": "N/A", "error": "No terminal ID provided"}
    else:
        try:
            ops = ContainerOps(DB_CONFIG)
            result = await asyncio.to_thread(ops.find_one, {"id": terminal_id, "user_id": user_id})
            container_data = result.data
            if not container_data:
                terminal_info = {
                    "id": terminal_id, "name": "Not Found", "ipAddress": "N/A", "port": "N/A",
                    "error": "Terminal not found or you don't have access",
                }
            else:
                env_vars = container_data.get("environment_vars") or {}
                ssh_username = env_vars.get("SSH_USERNAME", "")
                ssh_password = env_vars.get("SSH_PASSWORD", "")
                port_mappings = container_data.get("port_mappings") or []
                ssh_port = port_mappings[0].get("publish_port") if port_mappings else 2222
                terminal_info = {
                    "id": container_data.get("id"),
                    "name": container_data.get("name"),
                    "ipAddress": container_data.get("ip_address", "Pending..."),
                    "port": str(ssh_port),
                    "sshUsername": ssh_username,
                    "sshPassword": ssh_password,
                    "status": container_data.get("status", "Unknown"),
                    "saveStatus": container_data.get("save_status"),
                    "savedImage": container_data.get("saved_image"),
                    "saveError": container_data.get("save_error"),
                    "lastSavedAt": container_data.get("last_saved_at"),
                    "lastSaveAttemptedAt": container_data.get("last_save_attempted_at"),
                }
        except Exception:
            logger.error("error fetching terminal info", extra={"container_id": terminal_id}, exc_info=True)
            terminal_info = {"id": terminal_id, "name": "Error", "ipAddress": "N/A", "port": "N/A", "error": "Error loading terminal"}

    sse_token = await asyncio.to_thread(RedisSessionManager().create_sse_token, request.state.session_id)
    return templates.TemplateResponse(
        "terminalpage.html",
        {"request": request, "terminalInfo": terminal_info, "userInfo": request.state.user_info, "sseToken": sse_token},
    )


@require_page_session
async def profile(request: Request) -> HTMLResponse:
    '''GET /profile - fails open to no active device on any lookup error, same as Local's own
    version: a Profile page that can't resolve a device name should still render.'''
    active_device = None
    try:
        active_device = await _get_active_device(request.state.user_info["id"])
    except Exception:
        logger.error("could not fetch active device for profile page", exc_info=True)
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "userInfo": request.state.user_info, "activeDevice": active_device},
    )


@require_page_session
async def devices(request: Request) -> HTMLResponse:
    '''GET /devices - this user's registered devices, read-only. The richer device-linking
    approval UI (/device/link) is migration Part 4's own scope, not this one - see
    BROWSETERM_MIGRATION_PROGRESS.md.'''
    user_id = request.state.user_info["id"]
    device_ops = DeviceOps(DB_CONFIG)
    result = await asyncio.to_thread(device_ops.find, {"user_id": user_id})
    device_list = result.data if result.success else []
    return templates.TemplateResponse(
        "devices.html",
        {"request": request, "userInfo": request.state.user_info, "devices": device_list},
    )
