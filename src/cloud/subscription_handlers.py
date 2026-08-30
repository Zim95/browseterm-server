'''
Cloud subscription-resolution API.

Replaces Local's src/db_ops/subscription_db_ops.py:get_user_current_subscription_plan, which
used to chain get_or_create_free_subscription + get_current_subscription_plan against Postgres
directly. Server-to-server (X-Internal-Service-Token), same trust model as
container_handlers.py - Local already knows the authenticated user_id.
'''
import asyncio
from datetime import datetime, timedelta

from fastapi import Request
from fastapi.responses import JSONResponse

from browseterm_db.models.subscriptions import SubscriptionStatus
from browseterm_db.operations.all_operations import SubscriptionOps, SubscriptionTypeOps

from src.cloud.config import DB_CONFIG, CLOUD_INTERNAL_API_TOKEN
from src.common.logging_setup import get_logger

logger = get_logger("cloud_subscription_handlers")


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


async def get_current_subscription(request: Request) -> JSONResponse:
    '''
    GET /subscriptions/current?user_id=...

    Returns the caller's effective subscription TYPE (plan) dict, creating a free subscription
    first if they don't have one yet, and extending a free subscription's validity by a year on
    read (matching the previous behavior exactly).
    '''
    if not _internal_auth_ok(request):
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    try:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)

        subscription_ops = SubscriptionOps(DB_CONFIG)
        subscription_type_ops = SubscriptionTypeOps(DB_CONFIG)

        subscription_result = await asyncio.to_thread(subscription_ops.find_one, {"user_id": user_id})
        subscription = subscription_result.data
        if not subscription:
            types_result = await asyncio.to_thread(subscription_type_ops.find, {})
            free_type = next((t for t in (types_result.data or []) if t["type"] == "free"), None)
            if not free_type:
                return JSONResponse(content={"error": "No free subscription type configured"}, status_code=500)
            create_result = await asyncio.to_thread(subscription_ops.insert, {
                "user_id": user_id,
                "subscription_type_id": free_type["id"],
                "status": SubscriptionStatus.ACTIVE,
                "auto_renew": True,
                "valid_until": datetime.now() + timedelta(days=free_type["duration_days"]),
            })
            if not create_result.success:
                logger.error("free subscription creation failed", extra={"error": create_result.error})
                return JSONResponse(content={"error": "Error creating subscription"}, status_code=500)
            subscription = create_result.data

        subscription_type_result = await asyncio.to_thread(subscription_type_ops.find_one, {"id": subscription["subscription_type_id"]})
        subscription_type = subscription_type_result.data
        if not subscription_type:
            return JSONResponse(content={"error": "Subscription type not found"}, status_code=500)

        if subscription_type["type"] == "free":
            await asyncio.to_thread(subscription_ops.update, 
                {"id": subscription["id"]}, {"valid_until": datetime.now() + timedelta(days=365)}
            )

        return JSONResponse(content={"subscription_type": subscription_type})
    except Exception:
        logger.error("get current subscription failed", exc_info=True)
        return JSONResponse(content={"error": "Error resolving subscription"}, status_code=500)
