# builtins
from typing import Dict, Any, Optional
import asyncio
from functools import wraps

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import UserOps
from fastapi import Request
from fastapi.responses import RedirectResponse

# local
from src.authentication.session_manager import RedisSessionManager
from src.common.config import DB_CONFIG


def create_or_update_user(user_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    '''
    Create or update user in database.
    Args:
        user_info: Dictionary containing user information from OAuth provider
    Returns:
        Dict containing the user data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        user_ops: UserOps = UserOps(DB_CONFIG)
        filters: dict = {
            'provider_id': user_info.get('provider_id'),
            'provider': user_info.get('provider')
        }
        # find the user
        user: OperationResult = user_ops.find_one(filters)
        # raise error if any
        if user.error:
            raise Exception(user.error)
        # update the user if found
        if user.data:
            update_result: OperationResult = user_ops.update(
                filters=filters,
                data=user_info
            )
            if update_result.error:
                raise Exception(update_result.error)
            # find the updated user
            user: OperationResult = user_ops.find_one(filters)
            if user.error:
                raise Exception(user.error)
            return user.data
        # create the user if not found
        create_result: OperationResult = user_ops.insert(user_info)
        if create_result.error:
            raise Exception(create_result.error)
        return create_result.data
    except Exception as e:
        print(f"Error creating or updating user: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


def create_session(user_info: Dict[str, Any]) -> str:
    '''
    Create a session for the user.
    Args:
        user_info: Dictionary containing user information
    Returns:
        str: Session ID
    Raises:
        Exception: If session creation fails
    '''
    try:
        session_manager: RedisSessionManager = RedisSessionManager()
        session_id: str = session_manager.create_session(user_info)
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
    2. Create a session for the user
    Args:
        user_info: Dictionary containing user information
    Returns:
        Dict containing user info and session id
    Raises:
        Exception: If session creation fails
    '''
    try:
        user_info: Dict[str, Any] = await asyncio.to_thread(create_or_update_user, user_info)
        session_id: str = await asyncio.to_thread(create_session, user_info)
        return {
            'user_info': user_info,
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
        user_info: Optional[Dict[str, Any]] = session_manager.get_session(session_id)
        if not user_info:
            session_manager.delete_session(session_id)
            return RedirectResponse(url="/login", status_code=302)
        extend_session(session_id, expiry=1800) # 30 minutes
        # add user info and session id to request.state
        request.state.user_info = user_info
        request.state.session_id = session_id
        return await func(*args, **kwargs)
    return wrapper
