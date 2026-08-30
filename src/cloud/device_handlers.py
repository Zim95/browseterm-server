'''
Cloud Device API handlers (P05).

Authentication reuses the existing Redis-backed session mechanism
(`src.authentication.authentication_helpers.authenticate_session`) exactly as `app.py` already
does for every other authenticated handler -- no new auth architecture, no OAuth/session
migration (that's P07's job). Importing this decorator into Cloud code was verified not to pull
in Kubernetes/ContainerMaker/payment-gateway/`src.api_handlers`; see
`tests/integration/cloud/test_cloud_startup_independence.py` and CURRENT_TASK_STATE.md's P05
"Authentication boundary decision" section.

Device ownership invariant: every route that looks up an EXISTING device filters on both `id`
AND the authenticated session's `user_id` together (never `id` alone), and a lookup miss --
whether the id doesn't exist, is malformed, or belongs to another user -- always produces the
same 404 shape, so existence of another user's device is never leaked.
'''
import asyncio
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations.all_operations import DeviceOps

from src.authentication.authentication_helpers import authenticate_session
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
    At most one ACTIVE device per user at a time: the "which device is active for the user right
    now" the Desktop app owns (register/heartbeat both call this after making `active_device_id`
    ACTIVE). Every other currently-ACTIVE device of the same user is demoted to INACTIVE.
    REVOKED devices are left untouched -- demotion is only ever ACTIVE -> INACTIVE.

    Best-effort: a failure here does not fail the caller's request (the just-registered/
    heartbeated device's own state is already correct either way; a stale sibling ACTIVE status
    self-heals on that device's own next heartbeat).
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


@authenticate_session
async def register_device(request: Request) -> JSONResponse:
    '''
    POST /devices

    user_id is always the authenticated session's id. RegisterDeviceRequest does not declare a
    user_id (or any other identity/state) field, so a spoofed value in the body has nothing to
    bind to.
    '''
    try:
        request_data: dict = await request.json()
        try:
            body = RegisterDeviceRequest(**request_data)
        except ValidationError as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)

        user_id: str = request.state.user_info["id"]
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
        if not result.success:
            if result.error == _DUPLICATE_DEVICE_ERROR:
                return JSONResponse(content={"error": result.error}, status_code=409)
            logger.error("device registration failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error registering device"}, status_code=500)
        # A newly registered device defaults to ACTIVE (P01 model default) -- it becomes the
        # user's active device, demoting any other device they were previously using.
        await _demote_other_devices(device_ops, user_id, result.data["id"])
        return JSONResponse(content={"device": _serialize_device(result.data)}, status_code=201)
    except Exception:
        logger.error("device registration failed", exc_info=True)
        return JSONResponse(content={"error": "Error registering device"}, status_code=500)


@authenticate_session
async def list_devices(request: Request) -> JSONResponse:
    '''
    GET /devices

    Always scoped to the authenticated session's user_id -- never a query-string value.
    '''
    try:
        user_id: str = request.state.user_info["id"]
        device_ops = DeviceOps(DB_CONFIG)
        result = await asyncio.to_thread(device_ops.find, {"user_id": user_id})
        if not result.success:
            logger.error("device list failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error listing devices"}, status_code=500)
        return JSONResponse(content={"devices": [_serialize_device(d) for d in result.data]})
    except Exception:
        logger.error("device list failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing devices"}, status_code=500)


@authenticate_session
async def get_device(request: Request) -> JSONResponse:
    '''GET /devices/{device_id} -- ownership-scoped; nonexistent/foreign device both 404.'''
    try:
        user_id: str = request.state.user_info["id"]
        device_id: str = request.path_params["device_id"]
        device_ops = DeviceOps(DB_CONFIG)
        result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        if not result.data:
            return _device_not_found()
        return JSONResponse(content={"device": _serialize_device(result.data)})
    except Exception:
        logger.error("get device failed", exc_info=True)
        return JSONResponse(content={"error": "Error getting device"}, status_code=500)


@authenticate_session
async def update_device(request: Request) -> JSONResponse:
    '''
    POST /devices/{device_id}

    Partial update of machine/allocation metadata. Only keys allow-listed in
    UPDATABLE_DEVICE_FIELDS and actually present in the raw request body are ever written --
    id/user_id/used_*/status/registered_at/last_seen_at/revoked_at can never be reached from here
    regardless of what the client sends. Allocation <= total is validated using BOTH the existing
    stored values and the incoming changed values together.
    '''
    try:
        user_id: str = request.state.user_info["id"]
        device_id: str = request.path_params["device_id"]
        device_ops = DeviceOps(DB_CONFIG)

        existing = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
        if not existing.data:
            return _device_not_found()

        request_data: dict = await request.json()
        provided: dict = {k: v for k, v in request_data.items() if k in UPDATABLE_DEVICE_FIELDS}

        null_violations = sorted(k for k in provided if k in NON_NULLABLE_UPDATE_FIELDS and provided[k] is None)
        if null_violations:
            return JSONResponse(
                content={"error": f"{', '.join(null_violations)} cannot be null"},
                status_code=400,
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


@authenticate_session
async def heartbeat_device(request: Request) -> JSONResponse:
    '''
    POST /devices/{device_id}/heartbeat

    "This registered device is alive, and it's the one the user is using right now": ownership-
    scoped lookup, then server sets last_seen_at = now (UTC) and status = ACTIVE, and demotes
    every other of this user's ACTIVE devices to INACTIVE -- at most one device is "active for
    the user" at a time (see _demote_other_devices). The request body, if any, is never read --
    a client can never spoof last_seen_at. No offline-detection scheduler or resource
    reconciliation here; that's out of P05's scope.
    '''
    try:
        user_id: str = request.state.user_info["id"]
        device_id: str = request.path_params["device_id"]
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
