'''
Cloud OAuth start/callback, handoff redemption, and device-bootstrap handlers (P07 - p07.md).

Route map (registered in app.py):
    GET  /auth/{provider}/start     - public, redirects browser to Google/GitHub
    GET  /auth/{provider}/callback  - public (provider redirects here), redirects browser to
                                       Local with a one-time handoff code
    POST /auth/handoff/redeem       - public but possession-gated (needs a valid one-time code)
    POST /auth/device-bootstrap     - internal-token-gated (Local calls this server-to-server,
                                       after already verifying the caller's browser session)
    POST /auth/device-bootstrap/redeem - public but possession-gated, called by Desktop directly
'''
import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from src.authentication.authentication_helpers import process_user_info
from src.authentication.dto.session_dto import SessionResponseModel
from src.authentication.handoff_manager import HandoffManager
from src.authentication.oauth_state_manager import OAuthStateManager
from src.authentication.provider_oauth_service import PROVIDER_SERVICES, PROVIDER_AUTH_META_URLS, PROVIDER_SCOPES, \
    PROVIDER_CLIENT_IDS, PROVIDER_REDIRECT_URIS
from src.authentication.session_manager import RedisSessionManager
from src.authentication.device_token_manager import DeviceTokenManager
from src.cloud.config import CLOUD_INTERNAL_API_TOKEN
from src.cloud.device_data_models import RegisterDeviceRequest
from src.cloud.device_handlers import DeviceRegistrationError, _register_or_activate
from src.common.config import BROWSETERM_LOCAL_CALLBACK_URL
from src.common.logging_setup import get_logger

logger = get_logger("cloud_oauth_handlers")

# The only `target` values Cloud knows how to complete a login for, and the ONE destination each
# maps to server-side (p07.md section 10 - never taken from a caller-supplied redirect_uri).
_TARGET_CALLBACKS = {"local": BROWSETERM_LOCAL_CALLBACK_URL}


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(content={"error": message}, status_code=400)


async def oauth_start(request: Request) -> RedirectResponse:
    '''GET /auth/{provider}/start?target=local -- intentionally public (p07.md section 4): anyone
    may initiate OAuth, they will only ever authenticate as themselves.'''
    provider = request.path_params["provider"]
    if provider not in PROVIDER_SERVICES:
        return _bad_request("Unsupported provider")
    target = request.query_params.get("target", "local")
    if target not in _TARGET_CALLBACKS:
        return _bad_request("Unsupported target")

    state = await asyncio.to_thread(OAuthStateManager().create_state, provider, target)
    params = {
        "client_id": PROVIDER_CLIENT_IDS[provider],
        "redirect_uri": PROVIDER_REDIRECT_URIS[provider],
        "scope": PROVIDER_SCOPES[provider],
        "state": state,
        "response_type": "code",
    }
    from urllib.parse import urlencode
    return RedirectResponse(url=f"{PROVIDER_AUTH_META_URLS[provider]}?{urlencode(params)}", status_code=302)


async def oauth_callback(request: Request) -> RedirectResponse:
    '''GET /auth/{provider}/callback -- Google/GitHub redirect here directly (never to Local, never
    to Desktop - p07.md section 5). On any failure, sends the browser back to Local's login with
    a generic error rather than exposing internals.'''
    provider = request.path_params["provider"]
    error_target_login = f"{BROWSETERM_LOCAL_CALLBACK_URL.rsplit('/auth/callback', 1)[0]}/login"

    def _error_redirect(message: str) -> RedirectResponse:
        from urllib.parse import urlencode
        return RedirectResponse(
            url=f"{error_target_login}?{urlencode({'auth_result': 'error', 'error_message': message})}",
            status_code=302,
        )

    if provider not in PROVIDER_SERVICES:
        return _error_redirect("Unsupported provider")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    provider_error = request.query_params.get("error")
    if provider_error:
        return _error_redirect("Authentication was cancelled or denied")
    if not code or not state:
        return _error_redirect("Missing authorization code or state")

    state_data = await asyncio.to_thread(OAuthStateManager().consume_state, state, provider)
    if not state_data:
        return _error_redirect("Authentication state is expired or invalid")

    service = PROVIDER_SERVICES[provider]()
    try:
        user_info = await service.fetch_user_info(code)
    except Exception:
        logger.error("oauth callback: fetch_user_info failed", exc_info=True)
        return _error_redirect("Authentication failed")
    if not user_info:
        return _error_redirect("Authentication failed")

    try:
        session_response: SessionResponseModel = await process_user_info(user_info)
    except Exception:
        logger.error("oauth callback: session creation failed", exc_info=True)
        return _error_redirect("Could not create session")

    target = state_data["target"]
    callback_url = _TARGET_CALLBACKS.get(target, BROWSETERM_LOCAL_CALLBACK_URL)
    handoff_code = await asyncio.to_thread(
        HandoffManager().create_handoff, "local_login", session_response.user_info["id"], session_response.session_id
    )
    from urllib.parse import urlencode
    return RedirectResponse(url=f"{callback_url}?{urlencode({'code': handoff_code})}", status_code=302)


async def handoff_redeem(request: Request) -> JSONResponse:
    '''POST /auth/handoff/redeem -- public but possession-gated (p07.md section 26): the session
    was already created in oauth_callback, this just hands it back to whoever holds the one-time
    code (Local, redirected here by the browser).'''
    try:
        body = await request.json()
    except Exception:
        return _bad_request("Invalid JSON body")
    code = body.get("code")
    if not code:
        return _bad_request("code is required")

    data = await asyncio.to_thread(HandoffManager().consume_handoff, code, "local_login")
    if not data:
        return JSONResponse(content={"error": "Invalid or expired handoff code"}, status_code=401)

    session_id = data.get("session_id")
    if not session_id:
        return JSONResponse(content={"error": "Invalid handoff"}, status_code=401)
    validation = await asyncio.to_thread(RedisSessionManager().validate_session, session_id)
    if not validation.is_valid or not validation.session_data:
        return JSONResponse(content={"error": "Session no longer valid"}, status_code=401)

    return JSONResponse(content={
        "session_id": session_id,
        "user_info": validation.session_data.user_info,
        "subscription_info": validation.session_data.subscription_info,
        "current_subscription_plan": validation.session_data.current_subscription_plan,
    })


async def device_bootstrap_start(request: Request) -> JSONResponse:
    '''POST /auth/device-bootstrap -- internal-token-gated (p07.md section 21): Local calls this
    server-to-server, having already verified the browser session itself via the existing
    /auth/sessions/validate call. Local's word for user_id is trusted here the same way it's
    already trusted for /auth/sessions and the container/catalog APIs (see README's
    "Trust boundary" section) - this is not a new trust relationship, just a new use of the
    existing one.'''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return _bad_request("Invalid JSON body")
    user_id = body.get("user_id")
    if not user_id:
        return _bad_request("user_id is required")
    code = await asyncio.to_thread(HandoffManager().create_handoff, "device_bootstrap", user_id)
    return JSONResponse(content={"code": code})


async def device_bootstrap_redeem(request: Request) -> JSONResponse:
    '''POST /auth/device-bootstrap/redeem -- public but possession-gated, called directly by
    Desktop's native code with the code Local just handed it. Registers (or re-activates, on the
    P05 409-on-duplicate-name case) the device and issues its Bearer device token - the only
    place a device token is ever minted (p07.md section 21: "Do NOT make POST /devices anonymously
    writable... Cloud derives user_id from authenticated bootstrap/session context").'''
    try:
        body = await request.json()
    except Exception:
        return _bad_request("Invalid JSON body")
    code = body.get("code")
    device = body.get("device")
    if not code or not isinstance(device, dict):
        return _bad_request("code and device are required")

    data = await asyncio.to_thread(HandoffManager().consume_handoff, code, "device_bootstrap")
    if not data:
        return JSONResponse(content={"error": "Invalid or expired bootstrap code"}, status_code=401)
    user_id = data["user_id"]

    try:
        register_request = RegisterDeviceRequest(**device)
    except ValidationError as e:
        return _bad_request(str(e))

    try:
        serialized_device = await _register_or_activate(user_id, register_request)
    except DeviceRegistrationError as e:
        return JSONResponse(content={"error": e.message}, status_code=e.status_code)

    device_token = await asyncio.to_thread(
        DeviceTokenManager().issue_token,
        user_id,
        serialized_device["id"],
        ["device:read", "device:update", "device:heartbeat"],
    )
    return JSONResponse(content={"device": serialized_device, "device_token": device_token}, status_code=201)
