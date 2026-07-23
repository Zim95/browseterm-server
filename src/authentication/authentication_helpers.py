# builtins
from typing import Dict, Any, Optional
import asyncio
from functools import wraps

# modules
from fastapi import Request
from fastapi.responses import RedirectResponse

# local
from src.common.logging_setup import set_request_context
from src.authentication.session_manager import RedisSessionManager
from src.db_ops.user_db_ops import create_or_update_user
from src.db_ops.subscription_db_ops import get_or_create_free_subscription, get_current_subscription_plan

# dtos
from src.authentication.dto.session_dto import SessionDataModel, SessionResponseModel, SessionValidationModel
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.data_transformers.session_transformer import SessionInputTransformer, SessionResponseTransformer
from src.db_ops.dto.user_dto import CreateOrUpdateUserModel
from src.db_ops.dto.subscription_dto import GetOrCreateSubscriptionModel, GetSubscriptionPlanModel


def create_session(session_data: SessionDataModel) -> str:
    '''
    Create a session for the user.
    Args:
        session_data: SessionDataModel containing session information
    Returns:
        str: Session ID
    Raises:
        Exception: If session creation fails
    '''
    try:
        session_manager: RedisSessionManager = RedisSessionManager()
        session_id: str = session_manager.create_session(session_data)
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


async def process_user_info(user_info: UserInfoModel) -> SessionResponseModel:
    '''
    Process user info.
    1. Create or update the user in the database
    2. Get or create a free subscription for the user
    3. Create a session for the user
    Args:
        user_info: UserInfoModel containing user information
    Returns:
        SessionResponseModel containing user info and session id
    Raises:
        Exception: If session creation fails
    '''
    try:
        # Convert UserInfoModel to CreateOrUpdateUserModel for database operations
        create_user_model = CreateOrUpdateUserModel(
            provider_id=user_info.provider_id,
            provider=user_info.provider.value if hasattr(user_info.provider, 'value') else user_info.provider,
            name=user_info.name,
            email=user_info.email,
            profile_picture_url=user_info.profile_picture_url
        )
        # Database operations
        updated_user_info: Dict[str, Any] = await create_or_update_user(create_user_model)
        subscription_info: Dict[str, Any] = await get_or_create_free_subscription(
            GetOrCreateSubscriptionModel(user_id=updated_user_info['id'])
        )
        current_subscription_plan: Dict[str, Any] = await get_current_subscription_plan(
            GetSubscriptionPlanModel(
                subscription_id=subscription_info['id'],
                subscription_type_id=subscription_info['subscription_type_id']
            )
        )
        # Create session data model
        session_data: SessionDataModel = SessionInputTransformer.transform({
            'user_info': updated_user_info,
            'subscription_info': subscription_info,
            'current_subscription_plan': current_subscription_plan
        })
        # Create session
        session_id: str = await asyncio.to_thread(create_session, session_data)
        # Return SessionResponseModel
        return SessionResponseTransformer.transform(session_id, {
            'user_info': updated_user_info,
            'subscription_info': subscription_info,
            'current_subscription_plan': current_subscription_plan
        })
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

        # Validate session using the new validate_session method
        validation: SessionValidationModel = session_manager.validate_session(session_id)

        if not validation.is_valid or not validation.session_data:
            return RedirectResponse(url="/login", status_code=302)

        # Session is valid, extend it
        extend_session(session_id, expiry=1800)  # 30 minutes

        # Set the logging correlation context for this request: accept an inbound X-Request-Id
        # (else mint one) and record the acting user, so every log line in this handler — and any
        # gRPC call it makes — is tagged with the same request_id + user for cross-service tracing.
        ui = validation.session_data.user_info
        set_request_context(
            request_id=request.headers.get("X-Request-Id"),
            user=f"{getattr(ui, 'name', None) or 'user'}:{getattr(ui, 'email', None) or '-'}",
        )

        # Add session data to request.state
        request.state.user_info = validation.session_data.user_info
        request.state.subscription_info = validation.session_data.subscription_info
        request.state.current_subscription_plan = validation.session_data.current_subscription_plan
        request.state.session_id = session_id
        return await func(*args, **kwargs)
    return wrapper
