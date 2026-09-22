'''
Cloud browser session authentication (migration Part 3).

Cloud is now the browser origin and authenticates these requests directly - no more asking
Local to validate on its behalf over HTTP. Reuses the exact Redis-backed session/CSRF mechanics
browseterm-server-local's own src/authentication/authentication_service.py already established
(HttpOnly session cookie + a separate non-HttpOnly double-submit CSRF cookie minted at the same
time), just applied directly against Redis since Cloud already owns it, instead of hopping
through an HTTP call to itself the way Local had to.

Two distinct auth helpers on purpose, matching how Local itself already split this:
- `require_page_session` (decorator): for Jinja2 template routes. Redirects (302) to /login on a
  missing/invalid session - the right UX for a page load.
- `get_json_session`: for JSON API routes. Never redirects (see `auth_refresh`'s own reasoning,
  ported verbatim below) - a 302 on a fetch/XHR call is silently followed by the browser and hands
  the caller login-page HTML instead of a clean 401 signal.
'''
import secrets
from functools import wraps
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from src.authentication.session_manager import RedisSessionManager
from src.authentication.dto.session_dto import SessionDataModel
from src.common.config import COOKIE_SECURE, COOKIE_SAMESITE, SESSION_COOKIE_MAX_AGE
from src.common.logging_setup import set_request_context, get_logger

logger = get_logger("session_auth")

SESSION_COOKIE_NAME = "session"
CSRF_COOKIE_NAME = "csrf_token"


async def get_session_data(request: Request) -> Optional[SessionDataModel]:
    '''Validate the browser's session cookie directly against Redis, extending it on success
    (matches the previous decorator's validate-then-extend behavior). Never raises - a Redis
    error or a missing/expired/invalid session all return None.'''
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    manager = RedisSessionManager()
    validation = manager.validate_session(session_id)
    if not validation.is_valid or not validation.session_data:
        return None
    manager.extend_session(session_id, expiry=1800)
    return validation.session_data


def csrf_ok(request: Request) -> bool:
    '''Double-submit CSRF check (mirrors browseterm-server-local/src/api_handlers.py's own
    `_csrf_ok`) for cookie-authenticated state-changing routes: the non-HttpOnly csrf_token
    cookie set at login must be echoed back as a header by same-origin JS. A cross-site
    form/fetch riding the ambient session cookie cannot read that cookie to echo it, so this
    fails closed for it. Only ever applied to cookie-authenticated routes - device Bearer-token
    and internal-service-token requests carry no cookies at all and are a different trust
    boundary, not subject to this check.'''
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    return bool(header_token) and bool(cookie_token) and header_token == cookie_token


def set_session_cookies(response: Response, session_id: str) -> None:
    '''Sets both the HttpOnly session cookie and the deliberately-NOT-HttpOnly CSRF cookie
    together, exactly matching browseterm-server-local's authentication_service.py
    complete_login_from_handoff - the CSRF cookie's only job is proving a request came from
    same-origin JS, it is not a secret on its own.'''
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )


def clear_session_cookies(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value="", max_age=0, httponly=True,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME, value="", max_age=0, httponly=False,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE,
    )


def _apply_session_context(request: Request, session_data: SessionDataModel) -> None:
    user_info = session_data.user_info or {}
    set_request_context(
        request_id=request.headers.get("X-Request-Id"),
        user=f"{user_info.get('name') or 'user'}:{user_info.get('email') or '-'}",
    )
    request.state.user_info = user_info
    request.state.subscription_info = session_data.subscription_info
    request.state.current_subscription_plan = session_data.current_subscription_plan
    request.state.session_id = request.cookies.get(SESSION_COOKIE_NAME)


def require_page_session(handler):
    '''Decorator for Jinja2 template routes - see module docstring.'''
    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        session_data = await get_session_data(request)
        if not session_data:
            return RedirectResponse(url="/login", status_code=302)
        _apply_session_context(request, session_data)
        return await handler(request, *args, **kwargs)
    return wrapper


async def get_json_session(request: Request) -> Optional[SessionDataModel]:
    '''For JSON API routes - see module docstring. Also populates request.state on success, same
    as the page decorator, so downstream logging/handlers see a consistent shape either way.'''
    session_data = await get_session_data(request)
    if session_data:
        _apply_session_context(request, session_data)
    return session_data
