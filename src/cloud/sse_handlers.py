'''
P10 (see ~/browseterm/p.md's "P10" section): the browser connects HERE directly for real-time
container status/save-status updates - not through Local, which no longer relays or polls for
this at all (its old status_listener.py polling + /container-status-stream endpoint are removed
in the matching browseterm-server-local change).

Public route, but possession-gated by an sse_token (query string - EventSource cannot set custom
headers, so a header-based scheme isn't an option here) exactly like P11's ws-token-consume
endpoint: holding a valid token IS the authorization. Never trust a client-supplied user_id (the
plan's P10 section says this explicitly) - there isn't one in this design at all. The token
resolves only to a session_id (src/authentication/session_manager.py's
create_sse_token/validate_sse_token), and the user_id actually used to subscribe/scope the stream
is read from that session's own server-side data, the same trust boundary every other
session-authenticated route in this codebase uses.
'''
import asyncio
import json
from typing import AsyncGenerator

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.authentication.session_manager import RedisSessionManager
from src.cloud.sse_broadcaster import sse_broadcaster
from src.common.logging_setup import get_logger

logger = get_logger("cloud_sse_handlers")


async def events_stream(request: Request):
    '''
    GET /events/stream?token=<sse_token>

    Streams container status_change/save_status_change events for the token's owning user only.
    '''
    token = request.query_params.get("token")
    if not token:
        return JSONResponse(content={"error": "token is required"}, status_code=401)

    session_manager = RedisSessionManager()
    session_id = session_manager.validate_sse_token(token)
    if not session_id:
        return JSONResponse(content={"error": "Invalid or expired token"}, status_code=401)

    validation = session_manager.validate_session(session_id)
    if not validation.is_valid or not validation.session_data:
        return JSONResponse(content={"error": "Session expired"}, status_code=401)

    user_info = validation.session_data.user_info or {}
    user_id = user_info.get("id")
    if not user_id:
        return JSONResponse(content={"error": "Session has no user"}, status_code=401)

    async def event_generator() -> AsyncGenerator[str, None]:
        queue = sse_broadcaster.subscribe(user_id)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            sse_broadcaster.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
