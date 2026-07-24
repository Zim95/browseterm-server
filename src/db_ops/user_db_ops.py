'''
User database operations.
'''

# builtins
from typing import Dict, Any, Optional
import asyncio

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import UserOps
from browseterm_db.models.users import AuthProvider
from src.common.config import DB_CONFIG
from src.common.logging_setup import get_logger

# DTOs
from src.db_ops.dto.user_dto import CreateOrUpdateUserModel, GetUserModel

logger = get_logger("user_db_ops")


async def create_or_update_user(user_info: CreateOrUpdateUserModel) -> Optional[Dict[str, Any]]:
    '''
    Create or update user in database.
    Args:
        user_info: CreateOrUpdateUserModel containing user information from OAuth provider
    Returns:
        Dict containing the user data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        user_info_dict = user_info.to_dict()
        user_ops: UserOps = UserOps(DB_CONFIG)
        filters: dict = {
            'provider_id': user_info.provider_id,
            'provider': AuthProvider(user_info.provider)
        }
        # find the user
        user: OperationResult = await asyncio.to_thread(user_ops.find_one, filters)
        # raise error if any
        if user.error:
            raise Exception(user.error)
        # update the user if found
        if user.data:
            update_result: OperationResult = await asyncio.to_thread(
                user_ops.update,
                filters=filters,
                data=user_info_dict
            )
            if update_result.error:
                raise Exception(update_result.error)
            # find the updated user
            user: OperationResult = await asyncio.to_thread(user_ops.find_one, filters)
            if user.error:
                raise Exception(user.error)
            return user.data
        # create the user if not found
        create_result: OperationResult = await asyncio.to_thread(user_ops.insert, user_info_dict)
        if create_result.error:
            raise Exception(create_result.error)
        return create_result.data
    except Exception as e:
        logger.error("error creating or updating user", extra={"provider": user_info.provider, "provider_id": user_info.provider_id}, exc_info=True)
        raise Exception(f"Database operation failed: {str(e)}")
