'''
Database operations for subscriptions.
'''

# builtins
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import SubscriptionOps, SubscriptionTypeOps
from src.common.config import DB_CONFIG
from browseterm_db.models.subscriptions import SubscriptionStatus

# DTOs
from src.db_ops.dto.subscription_dto import (
    GetSubscriptionPlanModel,
    CreateFreeSubscriptionModel,
    GetOrCreateSubscriptionModel,
    GetUserSubscriptionPlanModel,
    UpdateSubscriptionModel
)


async def list_all_existing_subscription_types() -> Optional[List[Dict[str, Any]]]:
    '''
    List all existing subscription types.
    Returns:
        List containing the subscription type data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_type_ops: SubscriptionTypeOps = SubscriptionTypeOps(DB_CONFIG)
        subscription_types: OperationResult = await asyncio.to_thread(subscription_type_ops.find, filters={})  # find all
        if subscription_types.error:
            raise Exception(subscription_types.error)
        return subscription_types.data
    except Exception as e:
        print(f"Error listing all existing subscription types: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def get_current_subscription_plan(data: GetSubscriptionPlanModel) -> Optional[Dict[str, Any]]:
    '''
    Get the subscription plan based on subscription_type_id.
    If the subscription_type is free, extend subscription validity by 1 year using the subscription_id.
    Args:
        data: GetSubscriptionPlanModel containing subscription_id and subscription_type_id
    Returns:
        Dict containing the subscription plan data if successful, None if failed
    '''
    try:
        subscription_type_ops: SubscriptionTypeOps = SubscriptionTypeOps(DB_CONFIG)
        subscription_type: OperationResult = await asyncio.to_thread(subscription_type_ops.find_one, filters={'id': data.subscription_type_id})
        if subscription_type.error:
            raise Exception(subscription_type.error)
        # if the subscription_type is free, extend the subscription validity by 1 year
        if subscription_type.data['type'] == 'free':
            subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
            subscription_update: OperationResult = await asyncio.to_thread(
                subscription_ops.update,
                filters={'id': data.subscription_id}, data={'valid_until': datetime.now() + timedelta(days=365)}
            )
            if subscription_update.error:
                raise Exception(subscription_update.error)
        # return the subscription type data
        return subscription_type.data
    except Exception as e:
        print(f"Error getting current subscription plan: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def create_free_subscription(data: CreateFreeSubscriptionModel, subscription_types: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    '''
    Create a free subscription for a user.
    Args:
        data: CreateFreeSubscriptionModel containing user_id
        subscription_types: Subscription types if provided.
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        if not subscription_types:
            subscription_types: List[Dict[str, Any]] = await list_all_existing_subscription_types()
        free_subscription_type: Dict[str, Any] = [subscription_type for subscription_type in subscription_types if subscription_type['type'] == 'free'][0]
        result: OperationResult = await asyncio.to_thread(subscription_ops.insert, {
            "user_id": data.user_id,
            "subscription_type_id": free_subscription_type['id'],
            "status": SubscriptionStatus.ACTIVE,
            "auto_renew": True,
            "valid_until": datetime.now() + timedelta(days=free_subscription_type['duration_days'])
        })
        if result.error:
            raise Exception(result.error)
        return result.data
    except Exception as e:
        print(f"Error creating free subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def get_or_create_free_subscription(data: GetOrCreateSubscriptionModel, subscription_types: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    '''
    Get or create a subscription for a user.
    If the user already has a subscription, return it.
    If the user does not have a subscription, create a free plan.
    Args:
        data: GetOrCreateSubscriptionModel containing user_id
        subscription_types: Subscription types, optional
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        subscription: OperationResult = await asyncio.to_thread(subscription_ops.find_one, filters={'user_id': data.user_id})
        if subscription.error:
            raise Exception(subscription.error)
        if subscription.data:
            return subscription.data
        return await create_free_subscription(CreateFreeSubscriptionModel(user_id=data.user_id), subscription_types)
    except Exception as e:
        print(f"Error getting or creating subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def get_user_current_subscription_plan(data: GetUserSubscriptionPlanModel) -> Optional[Dict[str, Any]]:
    '''
    Get the current subscription plan of the user.
    Args:
        data: GetUserSubscriptionPlanModel containing user_id
    Returns:
        Dict containing the subscription plan data if successful, None if failed
    '''
    try:
        current_subscription_plan: Dict[str, Any] = await get_or_create_free_subscription(GetOrCreateSubscriptionModel(user_id=data.user_id))
        return await get_current_subscription_plan(GetSubscriptionPlanModel(
            subscription_id=current_subscription_plan['id'],
            subscription_type_id=current_subscription_plan['subscription_type_id']
        ))
    except Exception as e:
        print(f"Error getting user current subscription plan: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def update_subscription(data: UpdateSubscriptionModel) -> None:
    '''
    Update a subscription for a user.
    Args:
        data: UpdateSubscriptionModel containing user_id and subscription_type
    Returns:
        Dict containing the subscription data if successful, None if failed
    Raises:
        Exception: If database operation fails
    '''
    try:
        subscription_ops: SubscriptionOps = SubscriptionOps(DB_CONFIG)
        await asyncio.to_thread(subscription_ops.update_subscription, data.user_id, data.subscription_type)
    except Exception as e:
        print(f"Error updating subscription: {e}")
        raise Exception(f"Database operation failed: {str(e)}")
