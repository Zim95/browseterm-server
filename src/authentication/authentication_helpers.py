# builtins
from typing import Dict, Any, Optional
import asyncio
from functools import wraps

# modules
from fastapi import Request
from fastapi.responses import RedirectResponse

# local
from src.authentication.session_manager import RedisSessionManager
from src.db_ops.user_db_ops import create_or_update_user
from src.db_ops.subscription_db_ops import get_or_create_free_subscription, get_current_subscription_plan


def create_session(session_payload: Dict[str, Any]) -> str:
    '''
    Create a session for the user.
    Args:
        session_payload: Dictionary containing session information
    Returns:
        str: Session ID
    Raises:
        Exception: If session creation fails
    '''
    try:
        session_manager: RedisSessionManager = RedisSessionManager()
        session_id: str = session_manager.create_session(session_payload)
        return session_id
    except Exception as e:
        print(f"Error creating session: {e}")
        raise Exception(f"Error creating session: {str(e)}")


def extend_session(session_id: str, expiry: int | None = None) -> None:
    '''
    Extend the session expiry.
    Args:
        session_id: Session ID to extend
        expiry: Expiry time in seconds (defaults to 30 minutes)
    '''
    try:
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.extend_session(session_id, expiry)
    except Exception as e:
        print(f"Error extending session: {e}")
        raise Exception(f"Error extending session: {str(e)}")


async def process_user_info(user_info: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Process user info.
    1. Create or update the user in the database
    2. Get or create a free subscription for the user
    2. Create a session for the user
    Args:
        user_info: Dictionary containing user information
    Returns:
        Dict containing user info and session id
    Raises:
        Exception: If session creation fails
    '''
    try:
        updated_user_info: Dict[str, Any] = await asyncio.to_thread(create_or_update_user, user_info)
        subscription_info: Dict[str, Any] = await asyncio.to_thread(get_or_create_free_subscription, updated_user_info['id'])
        current_subscription_plan: Dict[str, Any] = await asyncio.to_thread(get_current_subscription_plan, subscription_info['id'], subscription_info['subscription_type_id'])
        session_payload: Dict[str, Any] = {
            'user_info': updated_user_info,
            'subscription_info': subscription_info,
            'current_subscription_plan': current_subscription_plan
        }
        session_id: str = await asyncio.to_thread(create_session, session_payload)
        return {
            'user_info': session_payload.get('user_info'),
            'subscription_info': session_payload.get('subscription_info'),
            'current_subscription_plan': session_payload.get('current_subscription_plan'),
            'session_id': session_id
        }
    except Exception as e:
        print(f"Error processing user info: {e}")
        raise Exception(f"Error processing user info: {str(e)}")


# this decorator can be used to authenticate the session
def authenticate_session(func: callable) -> callable:
    @wraps(func)
    async def wrapper(*args: tuple, **kwargs: dict) -> any:
        '''
        Authenticate the request using Redis session.
        If not authenticated, redirect to login page.
        '''
        request: Request = kwargs.get('request')
        session_id: str = request.cookies.get('session')
        if not session_id:
            return RedirectResponse(url="/login", status_code=302)
        session_manager: RedisSessionManager = RedisSessionManager()
        session_ttl: int = session_manager.get_session_ttl(session_id)
        # session does not exist
        if session_ttl == -2:
            return RedirectResponse(url="/login", status_code=302)
        # session exists but has expired (ttl == 0)
        if session_ttl == 0:
            session_manager.delete_session(session_id)
            return RedirectResponse(url="/login", status_code=302)
        # session exists and is valid (ttl > 0 or ttl == -1)
        session: Optional[Dict[str, Any]] = session_manager.get_session(session_id)
        user_info: Optional[Dict[str, Any]] = session.get('user_info')
        subscription_info: Optional[Dict[str, Any]] = session.get('subscription_info')
        current_subscription_plan: Optional[Dict[str, Any]] = session.get('current_subscription_plan')
        if not user_info:
            session_manager.delete_session(session_id)
            return RedirectResponse(url="/login", status_code=302)
        extend_session(session_id, expiry=1800) # 30 minutes
        # add user info and session id to request.state
        request.state.user_info = user_info
        request.state.subscription_info = subscription_info
        request.state.current_subscription_plan = current_subscription_plan
        request.state.session_id = session_id
        return await func(*args, **kwargs)
    return wrapper
