'''
Database operations for subscriptions.
'''

# builtins
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import SubscriptionOps, SubscriptionTypeOps
from src.common.config import DB_CONFIG
from browseterm_db.models.subscriptions import SubscriptionStatus


def list_all_existing_subscription_types() -> Optional[List[Dict[str, Any]]]:
    '''
    List all existing subscription types.
    Returns:
        List containing the subscription type data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_type_ops: SubscriptionTypeOps = SubscriptionTypeOps(DB_CONFIG)
        subscription_types: OperationResult = subscription_type_ops.find(filters={})  # find all
        if subscription_types.error:
            raise Exception(subscription_types.error)
        return subscription_types.data
    except Exception as e:
        print(f"Error listing all existing subscription types: {e}")
        raise Exception(f"Database operation failed: {str(e)}")

def get_current_subscription_plan(subscription_id: str, subscription_type_id: str) -> Optional[Dict[str, Any]]:
    '''
    Get the subscription plan based on subscription_type_id.
    If the subscription_type is free, extend subscription validity by 1 year using the subscription_id.
    Args:
        subscription_id: Subscription ID
        subscription_type_id: Subscription type ID
    Returns:
        Dict containing the subscription plan data if successful, None if failed
    '''
    try:
        subscription_type_ops: SubscriptionTypeOps = SubscriptionTypeOps(DB_CONFIG)
        subscription_type: OperationResult = subscription_type_ops.find_one(filters={'id': subscription_type_id})
        if subscription_type.error:
            raise Exception(subscription_type.error)
        # if the subscription_type is free, extend the subscription validity by 1 year
        if subscription_type.data['type'] == 'free':
            subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
            subscription_update: OperationResult = subscription_ops.update(filters={'id': subscription_id}, data={'valid_until': datetime.now() + timedelta(days=365)})
            if subscription_update.error:
                raise Exception(subscription_update.error)
        # return the subscription type data
        return subscription_type.data
    except Exception as e:
        print(f"Error getting current subscription plan: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


def create_free_subscription(user_id: str, subscrption_types: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    '''
    Create a free subscription for a user.
    Args:
        user_id: User ID
        subscription_types: Subscription type if provided.
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        if not subscrption_types:
            subscrption_types: List[Dict[str, Any]] = list_all_existing_subscription_types()
        free_subscription_type: Dict[str, Any] = [subscription_type for subscription_type in subscrption_types if subscription_type['type'] == 'free'][0]
        return subscription_ops.insert({
            "user_id": user_id,
            "subscription_type_id": free_subscription_type['id'],
            "status": SubscriptionStatus.ACTIVE,
            "auto_renew": True,
            "valid_until": datetime.now() + timedelta(days=free_subscription_type['duration_days'])
        })
    except Exception as e:
        print(f"Error creating free subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


def get_or_create_free_subscription(user_id: str, subscription_types: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    '''
    Get or create a subscription for a user.
    If the user already has a subscription, return it.
    If the user does not have a subscription, create a free plan.
    Args:
        user_id: User ID
        subscription_types: Subscription types, optional
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        subscription: OperationResult = subscription_ops.find_one(filters={'user_id': user_id})
        if subscription.error:
            raise Exception(subscription.error)
        if subscription.data:
            return subscription.data
        return create_free_subscription(user_id, subscription_types)
    except Exception as e:
        print(f"Error getting or creating subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


def update_subscription(user_id: str, subscription_type: str) -> None:
    '''
    Update a subscription for a user.
    Args:
        user_id: User ID
        subscription_type: Subscription type
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        subscription_ops.update_subscription(user_id, subscription_type)
    except Exception as e:
        print(f"Error updating subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")
