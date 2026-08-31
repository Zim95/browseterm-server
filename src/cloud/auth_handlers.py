'''
Cloud session/auth API.

This is the replacement for Local's direct Redis/Postgres session access. Local
(browseterm-server-local) holds no DB/Redis client at all as of this task: OAuth token exchange
still happens in Local (talking to Google/GitHub directly - no DB involved in that step), but
turning that OAuth profile into a *session* - creating/updating the user row, resolving their
subscription, and writing the Redis session - now happens here, on Cloud, the only process
allowed to touch Postgres/Redis directly. Every subsequent authenticated request Local receives
is validated by calling back here instead of reading Redis itself.

Internal-service auth (interim): POST /auth/sessions is the one route that can mint a session
for an arbitrary user, so it requires a shared secret (CLOUD_INTERNAL_API_TOKEN) that only Local
knows, via the X-Internal-Service-Token header - a stand-in for the full "Cloud is the OAuth
client" redesign (plan section 7.1 / P07), which removes the need for this endpoint to trust
Local's word for who the user is at all. Documented as interim in README.md.
'''
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.authentication.authentication_helpers import extend_session, process_user_info
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.session_manager import RedisSessionManager
from src.cloud.config import CLOUD_INTERNAL_API_TOKEN
from src.common.logging_setup import get_logger

logger = get_logger("cloud_auth_handlers")


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


async def create_session_from_user_info(request: Request) -> JSONResponse:
    '''
    POST /auth/sessions

    Local calls this right after it completes an OAuth token exchange with Google/GitHub,
    handing Cloud the resulting profile. Cloud creates/updates the user, resolves their
    subscription, and issues a Redis session.
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
        try:
            user_info = UserInfoModel(**body)
        except ValidationError as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)
        session_response = await process_user_info(user_info)
        return JSONResponse(content=session_response.model_dump(mode="json"), status_code=201)
    except Exception:
        logger.error("session creation failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating session"}, status_code=500)


async def validate_session(request: Request) -> JSONResponse:
    '''
    POST /auth/sessions/validate

    Body: {"session_id": "..."}. Local's authenticate_session replacement calls this on every
    authenticated request instead of touching Redis itself. A valid session is transparently
    extended (matching the previous in-process decorator's behavior).
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(content={"is_valid": False}, status_code=400)

        session_manager = RedisSessionManager()
        validation = session_manager.validate_session(session_id)
        if not validation.is_valid or not validation.session_data:
            return JSONResponse(content={"is_valid": False})

        extend_session(session_id, expiry=1800)
        return JSONResponse(content={
            "is_valid": True,
            "user_info": validation.session_data.user_info,
            "subscription_info": validation.session_data.subscription_info,
            "current_subscription_plan": validation.session_data.current_subscription_plan,
        })
    except Exception:
        logger.error("session validation failed", exc_info=True)
        return JSONResponse(content={"is_valid": False, "error": "Error validating session"}, status_code=500)


async def create_websocket_token(request: Request) -> JSONResponse:
    '''
    POST /auth/websocket-tokens

    Body: {"session_id": "..."}. Wraps RedisSessionManager.create_websocket_token exactly as-is
    (one-time, 60s-TTL token linking to the session, validated/consumed by socket-ssh) - Local's
    terminal-page handler calls this instead of touching Redis itself.
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(content={"error": "session_id is required"}, status_code=400)
        session_manager = RedisSessionManager()
        token = session_manager.create_websocket_token(session_id)
        return JSONResponse(content={"token": token})
    except Exception:
        logger.error("websocket token creation failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating websocket token"}, status_code=500)


async def consume_websocket_token(request: Request) -> JSONResponse:
    '''
    POST /auth/websocket-tokens/consume

    P11 (see ~/browseterm/p.md's "P11" section) - migrates socket-ssh off its own direct Redis
    access. Public but possession-gated, same pattern as P07's handoff/device-bootstrap
    redemption (p07.md): holding a valid one-time ws_token IS the authorization, no
    internal-service-token needed - socket-ssh has no such shared secret and shouldn't need one
    just to consume a token a real user's browser was already handed.

    Body: {"token": "..."}. Atomically consumes the token (GETDEL - single-use) and verifies the
    linked session is still valid, reproducing socket-ssh's former two-step
    "token exists -> delete -> session still exists" check as one Cloud call.
    '''
    try:
        body = await request.json()
        token = body.get("token")
        if not token:
            return JSONResponse(content={"valid": False, "error": "token is required"}, status_code=400)

        session_manager = RedisSessionManager()
        session_id = session_manager.consume_websocket_token(token)
        if not session_id:
            return JSONResponse(content={"valid": False, "error": "Invalid or expired token"}, status_code=401)

        validation = session_manager.validate_session(session_id)
        if not validation.is_valid or not validation.session_data:
            return JSONResponse(content={"valid": False, "error": "Session expired"}, status_code=401)

        user_info = validation.session_data.user_info or {}
        return JSONResponse(content={"valid": True, "session_id": session_id, "user_id": user_info.get("id")})
    except Exception:
        logger.error("websocket token consumption failed", exc_info=True)
        return JSONResponse(content={"valid": False, "error": "Error validating websocket token"}, status_code=500)


async def create_sse_token(request: Request) -> JSONResponse:
    '''
    POST /auth/sse-tokens

    P10 (see ~/browseterm/p.md's "P10" section). Body: {"session_id": "..."}. Wraps
    RedisSessionManager.create_sse_token exactly as-is - Local's terminals/terminalpage handlers
    call this instead of touching Redis themselves, same shape as create_websocket_token, but the
    resulting token is read-only-validated (not consumed) by src/cloud/sse_handlers.py, since the
    browser's EventSource presents it again on every automatic reconnect.
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(content={"error": "session_id is required"}, status_code=400)
        session_manager = RedisSessionManager()
        token = session_manager.create_sse_token(session_id)
        return JSONResponse(content={"token": token})
    except Exception:
        logger.error("sse token creation failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating sse token"}, status_code=500)


async def delete_session(request: Request) -> JSONResponse:
    '''
    POST /auth/sessions/delete

    Body: {"session_id": "..."}. Local's logout handler calls this instead of touching Redis
    directly.
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        body = await request.json()
        session_id = body.get("session_id")
        if session_id:
            session_manager = RedisSessionManager()
            session_manager.delete_session(session_id)
        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("session deletion failed", exc_info=True)
        return JSONResponse(content={"error": "Error deleting session"}, status_code=500)
