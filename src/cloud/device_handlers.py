'''
Cloud Device API handlers (P05, migrated to device-token auth in P07 - see p07.md).

P07 change: these routes used to be session-cookie-authenticated (authenticate_session, shared
with the browser). They are now authenticated with a per-device Bearer token
(authenticate_device, src.authentication.device_token_manager) instead - p07.md section 16/20
requires the browser session and the native device credential be different credentials.
`POST /devices` (register) is no longer an independently reachable route at all: there is no
device token yet at registration time (chicken-and-egg), so registration now only happens inside
device-bootstrap redemption (src/cloud/oauth_handlers.py:device_bootstrap_redeem), which derives
user_id from a one-time handoff instead of any device-supplied credential. `_register_or_activate`
below is that shared registration/re-activation logic, called from both places it's still needed.

Device ownership invariant unchanged: every route scopes to `device_id` AND the token's own
`user_id`/`device_id` together, and a lookup miss - whether the id doesn't exist, is malformed,
belongs to another user, or (new in P07) belongs to a *different device's own token* - always
produces the same 404 shape (p07.md section 18/25: "D1 token cannot operate as D2").
'''
import asyncio
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations.all_operations import DeviceOps

from src.authentication.device_token_manager import DeviceTokenManager
from src.cloud.config import DB_CONFIG
from src.cloud.device_data_models import (
    NON_NULLABLE_UPDATE_FIELDS,
    UPDATABLE_DEVICE_FIELDS,
    RegisterDeviceRequest,
    UpdateDeviceRequest,
)
from src.common.logging_setup import get_logger

logger = get_logger("cloud_device_handlers")

# The exact string DeviceOps.insert() returns when the (user_id, device_name) unique constraint
# (or, in principle, an invalid user_id FK -- not reachable here since user_id always comes from
# an authenticated session) is violated. See browseterm_db/operations/device_ops.py.
_DUPLICATE_DEVICE_ERROR = "User not found or device name already registered for this user"


def _device_not_found() -> JSONResponse:
    return JSONResponse(content={"error": "Device not found"}, status_code=404)


def _unauthorized() -> JSONResponse:
    return JSONResponse(content={"error": "Unauthorized"}, status_code=401)


def _serialize_device(device: dict) -> dict:
    '''Adds derived available_* fields (allocated - used). Never persisted -- see P01.'''
    return {
        **device,
        "available_cpu": device["allocated_cpu"] - device["used_cpu"],
        "available_memory_bytes": device["allocated_memory_bytes"] - device["used_memory_bytes"],
        "available_storage_bytes": device["allocated_storage_bytes"] - device["used_storage_bytes"],
    }


async def _demote_other_devices(device_ops: DeviceOps, user_id: str, active_device_id: str) -> None:
    '''
    At most one ACTIVE device per user at a time. Best-effort: a failure here does not fail the
    caller's request.
    '''
    result = await asyncio.to_thread(device_ops.find, {"user_id": user_id, "status": DeviceStatus.ACTIVE})
    if not result.success:
        logger.error("could not list devices to demote", extra={"error": result.error})
        return
    for device in result.data:
        if device["id"] == active_device_id:
            continue
        demote_result = await asyncio.to_thread(
            device_ops.update, {"id": device["id"], "user_id": user_id}, {"status": DeviceStatus.INACTIVE}
        )
        if not demote_result.success:
            logger.error(
                "could not demote sibling device",
                extra={"device_id": device["id"], "error": demote_result.error},
            )


class DeviceRegistrationError(Exception):
    '''Raised by _register_or_activate for a caller (device_bootstrap_redeem) to translate into
    its own JSONResponse shape.'''

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def _register_or_activate(user_id: str, body: RegisterDeviceRequest) -> dict:
    '''
    Shared by device-bootstrap redemption (new device or an existing device re-bootstrapping,
    e.g. after its token expired) and (not currently reachable via HTTP, kept for the
    re-activation semantics P05 already established) direct callers: register a new device, or -
    on the P05 non-idempotent 409-on-duplicate-name case - fall back to re-activating the
    existing device of that name via the same heartbeat semantics register would have produced
    (ACTIVE, siblings demoted). Returns the serialized device. Raises DeviceRegistrationError on
    any real failure.
    '''
    device_ops = DeviceOps(DB_CONFIG)
    insert_data = {
        "user_id": user_id,
        "device_name": body.device_name,
        "os": body.os,
        "architecture": body.architecture,
        "runtime_version": body.runtime_version,
        "total_cpu": body.total_cpu,
        "total_memory_bytes": body.total_memory_bytes,
        "total_storage_bytes": body.total_storage_bytes,
        "allocated_cpu": body.allocated_cpu,
        "allocated_memory_bytes": body.allocated_memory_bytes,
        "allocated_storage_bytes": body.allocated_storage_bytes,
        "gpu_info": body.gpu_info,
    }
    result = await asyncio.to_thread(device_ops.insert, insert_data)
    if result.success:
        await _demote_other_devices(device_ops, user_id, result.data["id"])
        return _serialize_device(result.data)

    if result.error != _DUPLICATE_DEVICE_ERROR:
        logger.error("device registration failed", extra={"error": result.error})
        raise DeviceRegistrationError(500, "Error registering device")

    existing = await asyncio.to_thread(device_ops.find_one, {"user_id": user_id, "device_name": body.device_name})
    if not existing.data:
        raise DeviceRegistrationError(409, result.error)
    device_id = existing.data["id"]
    heartbeat_result = await asyncio.to_thread(
        device_ops.update,
        {"id": device_id, "user_id": user_id},
        {"last_seen_at": datetime.now(timezone.utc), "status": DeviceStatus.ACTIVE},
    )
    if not heartbeat_result.success:
        logger.error("device re-activation failed", extra={"error": heartbeat_result.error})
        raise DeviceRegistrationError(500, "Error activating device")
    await _demote_other_devices(device_ops, user_id, device_id)
    updated = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
    return _serialize_device(updated.data)


def authenticate_device(func: callable) -> callable:
    '''
    Bearer device-token auth (p07.md section 20/23). Replaces authenticate_session on the Device
    API. Sets request.state.user_id/device_id/scopes from the token - never trusts a
    client-supplied user_id/device_id anywhere (matches the existing P03/P05 pattern, just with a
    different credential source).
    '''
    @wraps(func)
    async def wrapper(*args: tuple, **kwargs: dict) -> any:
        request: Request = kwargs.get('request')
        auth_header: Optional[str] = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return _unauthorized()
        raw_token = auth_header[len("Bearer "):].strip()
        if not raw_token:
            return _unauthorized()

        token_data = await asyncio.to_thread(DeviceTokenManager().validate_token, raw_token)
        if not token_data:
            return _unauthorized()

        request.state.user_id = token_data["user_id"]
        request.state.device_id = token_data["device_id"]
        request.state.scopes = token_data.get("scopes", [])
        return await func(*args, **kwargs)
    return wrapper


@authenticate_device
async def list_devices(request: Request) -> JSONResponse:
    '''
    GET /devices

    A device token is scoped to exactly one device (p07.md section 16-18) - this intentionally
    returns only that one device, not "all of this user's devices" (that would need
    user-session auth, out of scope here; nothing currently calls this needing more).
    '''
    try:
        device_ops = DeviceOps(DB_CONFIG)
        result = await asyncio.to_thread(
            device_ops.find_one, {"id": request.state.device_id, "user_id": request.state.user_id}
        )
        if not result.data:
            return JSONResponse(content={"devices": []})
        return JSONResponse(content={"devices": [_serialize_device(result.data)]})
    except Exception:
        logger.error("device list failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing devices"}, status_code=500)


@authenticate_device
async def get_device(request: Request) -> JSONResponse:
    '''GET /devices/{device_id} -- token-scoped; any id other than the token's own device_id is a
    404, identical to a nonexistent device (p07.md section 18/25).'''
    try:
        device_id: str = request.path_params["device_id"]
        if device_id != request.state.device_id:
            return _device_not_found()
        device_ops = DeviceOps(DB_CONFIG)
        result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": request.state.user_id})
        if not result.data:
            return _device_not_found()
        return JSONResponse(content={"device": _serialize_device(result.data)})
    except Exception:
        logger.error("get device failed", exc_info=True)
        return JSONResponse(content={"error": "Error getting device"}, status_code=500)


@authenticate_device
async def update_device(request: Request) -> JSONResponse:
    '''POST /devices/{device_id} -- token-scoped, same 404-on-mismatch as get_device.'''
    try:
        device_id: str = request.path_params["device_id"]
        if device_id != request.state.device_id:
            return _device_not_found()
        user_id = request.state.user_id
        device_ops = DeviceOps(DB_CONFIG)

        existing = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        if not existing.data:
            return _device_not_found()

        request_data: dict = await request.json()
        provided: dict = {k: v for k, v in request_data.items() if k in UPDATABLE_DEVICE_FIELDS}

        null_violations = sorted(k for k in provided if k in NON_NULLABLE_UPDATE_FIELDS and provided[k] is None)
        if null_violations:
            return JSONResponse(
                content={"error": f"{', '.join(null_violations)} cannot be null"}, status_code=400
            )

        try:
            validated = UpdateDeviceRequest(**provided)
        except ValidationError as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)
        update_data: dict = {k: getattr(validated, k) for k in provided}

        effective_total_cpu = update_data.get("total_cpu", existing.data["total_cpu"])
        effective_total_memory = update_data.get("total_memory_bytes", existing.data["total_memory_bytes"])
        effective_total_storage = update_data.get("total_storage_bytes", existing.data["total_storage_bytes"])
        effective_allocated_cpu = update_data.get("allocated_cpu", existing.data["allocated_cpu"])
        effective_allocated_memory = update_data.get("allocated_memory_bytes", existing.data["allocated_memory_bytes"])
        effective_allocated_storage = update_data.get("allocated_storage_bytes", existing.data["allocated_storage_bytes"])

        allocation_errors = []
        if effective_allocated_cpu > effective_total_cpu:
            allocation_errors.append("allocated_cpu cannot exceed total_cpu")
        if effective_allocated_memory > effective_total_memory:
            allocation_errors.append("allocated_memory_bytes cannot exceed total_memory_bytes")
        if effective_allocated_storage > effective_total_storage:
            allocation_errors.append("allocated_storage_bytes cannot exceed total_storage_bytes")
        if allocation_errors:
            return JSONResponse(content={"error": allocation_errors}, status_code=400)

        if not update_data:
            return JSONResponse(content={"device": _serialize_device(existing.data)})

        result = await asyncio.to_thread(device_ops.update, {"id": device_id, "user_id": user_id}, update_data)
        if not result.success:
            logger.error("device update failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error updating device"}, status_code=500)

        updated = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        return JSONResponse(content={"device": _serialize_device(updated.data)})
    except Exception:
        logger.error("device update failed", exc_info=True)
        return JSONResponse(content={"error": "Error updating device"}, status_code=500)


@authenticate_device
async def heartbeat_device(request: Request) -> JSONResponse:
    '''POST /devices/{device_id}/heartbeat -- token-scoped, same 404-on-mismatch.'''
    try:
        device_id: str = request.path_params["device_id"]
        if device_id != request.state.device_id:
            return _device_not_found()
        user_id = request.state.user_id
        device_ops = DeviceOps(DB_CONFIG)

        existing = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        if not existing.data:
            return _device_not_found()

        result = await asyncio.to_thread(
            device_ops.update,
            {"id": device_id, "user_id": user_id},
            {"last_seen_at": datetime.now(timezone.utc), "status": DeviceStatus.ACTIVE},
        )
        if not result.success:
            logger.error("device heartbeat failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error updating device heartbeat"}, status_code=500)

        await _demote_other_devices(device_ops, user_id, device_id)

        updated = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        return JSONResponse(content={"device": _serialize_device(updated.data)})
    except Exception:
        logger.error("device heartbeat failed", exc_info=True)
        return JSONResponse(content={"error": "Error updating device heartbeat"}, status_code=500)
