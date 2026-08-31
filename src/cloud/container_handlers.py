'''
Cloud container/workspace metadata API.

Replaces Local's direct `ContainerOps(DB_CONFIG)` access (src/db_ops/container_db_ops.py and the
6 direct call sites that used to live in src/api_handlers.py). Called server-to-server by
browseterm-server-local, which has already authenticated the end user itself via
src.cloud.auth_handlers.validate_session and is passing along a trusted `user_id` - NOT called
directly by a browser, so there's no session cookie here. Auth is the same interim
X-Internal-Service-Token shared secret as auth_handlers.py (see that module's docstring for why
this is interim, not the final design).

Ownership is still enforced on every write/read: every lookup of an EXISTING container filters
on {id, user_id} together (matching P03's ownership hardening exactly), never id alone.
'''
import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from browseterm_db.models.containers import ContainerStatus
from browseterm_db.operations.all_operations import ContainerOps, ImageOps, SubscriptionTypeOps

from src.cloud.config import DB_CONFIG, CLOUD_INTERNAL_API_TOKEN
from src.common.logging_setup import get_logger

logger = get_logger("cloud_container_handlers")

# Mirrors the previous UpdateContainerDBData allow-list (container_db_ops.py /
# api_handlers.update_container) - id/user_id/created_at are never writable via this route.
UPDATABLE_CONTAINER_FIELDS = {
    "image_id", "name", "status", "cpu_limit", "memory_limit", "storage_limit", "ip_address",
    "port_mappings", "environment_vars", "associated_resources", "kubernetes_id", "saved_image",
    "save_status", "save_error", "last_saved_at", "last_save_attempted_at", "last_active_at",
    "device_id",
}


def _internal_auth_ok(request: Request) -> bool:
    return request.headers.get("X-Internal-Service-Token") == CLOUD_INTERNAL_API_TOKEN


def _unauthorized() -> JSONResponse:
    return JSONResponse(content={"error": "Unauthorized"}, status_code=401)


def _not_found() -> JSONResponse:
    return JSONResponse(content={"error": "Container not found"}, status_code=404)


async def create_container(request: Request) -> JSONResponse:
    '''POST /containers - body must include user_id (Local-trusted, not client-trusted).'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        body = await request.json()
        user_id = body.get("user_id")
        name = body.get("name")
        if not user_id or not name:
            return JSONResponse(content={"error": "user_id and name are required"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"name": name, "user_id": user_id})
        if existing.data:
            return JSONResponse(
                content={"error": f"Container with name '{name}' already exists for this user."},
                status_code=409,
            )

        insert_data = {k: v for k, v in body.items() if k != "id"}
        result = await asyncio.to_thread(ops.insert, insert_data)
        if not result.success:
            logger.error("container create failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error creating container"}, status_code=500)
        return JSONResponse(content={"container": result.data}, status_code=201)
    except Exception:
        logger.error("container create failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating container"}, status_code=500)


async def get_container(request: Request) -> JSONResponse:
    '''GET /containers/{container_id}?user_id=...'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        user_id = request.query_params.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)
        ops = ContainerOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        if not result.data:
            return _not_found()
        return JSONResponse(content={"container": result.data})
    except Exception:
        logger.error("get container failed", exc_info=True)
        return JSONResponse(content={"error": "Error getting container"}, status_code=500)


async def list_containers(request: Request) -> JSONResponse:
    '''GET /containers?user_id=...&limit=&offset='''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)
        limit = request.query_params.get("limit")
        offset = request.query_params.get("offset")
        ops = ContainerOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.find, 
            {"user_id": user_id},
            limit=int(limit) if limit else None,
            offset=int(offset) if offset else None,
        )
        if not result.success:
            logger.error("list containers failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error listing containers"}, status_code=500)
        return JSONResponse(content={"containers": result.data})
    except Exception:
        logger.error("list containers failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing containers"}, status_code=500)


async def update_container(request: Request) -> JSONResponse:
    '''
    POST /containers/{container_id}

    Body must include user_id (Local-trusted). Only UPDATABLE_CONTAINER_FIELDS keys present in
    the body are ever written.
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        if not existing.data:
            return _not_found()

        update_data = {k: v for k, v in body.items() if k in UPDATABLE_CONTAINER_FIELDS}
        if not update_data:
            return JSONResponse(content={"container": existing.data})

        result = await asyncio.to_thread(ops.update, {"id": container_id, "user_id": user_id}, update_data)
        if not result.success:
            logger.error("container update failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error updating container"}, status_code=500)

        updated = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        return JSONResponse(content={"container": updated.data})
    except Exception:
        logger.error("container update failed", exc_info=True)
        return JSONResponse(content={"error": "Error updating container"}, status_code=500)


async def delete_container(request: Request) -> JSONResponse:
    '''POST /containers/{container_id}/delete - body must include user_id (Local-trusted).'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        if not existing.data:
            return _not_found()

        result = await asyncio.to_thread(ops.delete, {"id": container_id, "user_id": user_id})
        if not result.success:
            logger.error("container delete failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error deleting container"}, status_code=500)
        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("container delete failed", exc_info=True)
        return JSONResponse(content={"error": "Error deleting container"}, status_code=500)


async def update_container_status(request: Request) -> JSONResponse:
    '''
    POST /internal/containers/{container_id}/status

    P09 - migrates `status_monitor` (browseterm_workload) off direct Postgres access onto this
    endpoint. Deliberately separate from the user-scoped `/containers/{id}` update above: this
    caller (status_monitor) has no `user_id` at all - it's a trusted, cluster-wide SYSTEM caller
    (watches every user's pods), not acting on behalf of any specific user's request, so there is
    no ownership scoping to apply here (matches p07.md's principle of authenticating workloads as
    a trusted service rather than trying to force-fit a user-scoped credential onto a background
    job - see p.md's P09 section).

    Body: {"status": "<ContainerStatus value>", "expected_status": "<ContainerStatus value>"?}.
    Mirrors status_monitor's own former direct-DB write exactly: `expected_status`, if given,
    makes this an atomic conditional UPDATE (WHERE id=... AND status=expected_status) - a
    compare-and-swap, not a read-then-write, matching the old `mark_lost_if_running`'s exact
    semantics (a filter that doesn't match affects zero rows and is a success, not an error -
    intentionally not distinguished from "container_id doesn't exist at all", exactly as the
    direct-DB version never distinguished them either).
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        body = await request.json()
        status = body.get("status")
        if not status:
            return JSONResponse(content={"error": "status is required"}, status_code=400)
        try:
            new_status = ContainerStatus(status)
        except ValueError:
            return JSONResponse(content={"error": f"Invalid status: {status}"}, status_code=400)

        filters = {"id": container_id}
        expected_status = body.get("expected_status")
        if expected_status:
            try:
                filters["status"] = ContainerStatus(expected_status)
            except ValueError:
                return JSONResponse(content={"error": f"Invalid expected_status: {expected_status}"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.update, filters, {"status": new_status})
        if not result.success:
            logger.error(
                "container status update failed",
                extra={"container_id": container_id, "error": result.error},
            )
            return JSONResponse(content={"error": "Error updating container status"}, status_code=500)
        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("container status update failed", exc_info=True)
        return JSONResponse(content={"error": "Error updating container status"}, status_code=500)


async def list_images(request: Request) -> JSONResponse:
    '''GET /catalog/images - read-only, no ownership scoping (images are global). Matches the
    pre-migration Local behavior of only returning active images.'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        ops = ImageOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.find, {"is_active": True})
        if not result.success:
            logger.error("list images failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error listing images"}, status_code=500)
        return JSONResponse(content={"images": result.data})
    except Exception:
        logger.error("list images failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing images"}, status_code=500)


async def list_subscription_types(request: Request) -> JSONResponse:
    '''GET /catalog/subscription-types - read-only, no ownership scoping.'''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        ops = SubscriptionTypeOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.find, {})
        if not result.success:
            logger.error("list subscription types failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error listing subscription types"}, status_code=500)
        return JSONResponse(content={"subscription_types": result.data})
    except Exception:
        logger.error("list subscription types failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing subscription types"}, status_code=500)
