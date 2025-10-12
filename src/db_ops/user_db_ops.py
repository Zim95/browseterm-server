'''
User database operations.
'''

# builtins
from typing import Dict, Any, Optional

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import UserOps
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
