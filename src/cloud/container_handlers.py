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
from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations.all_operations import ContainerOps, DeviceOps, ImageOps, SubscriptionTypeOps

from src.cloud.config import DB_CONFIG, CLOUD_INTERNAL_API_TOKEN
from src.cloud.resource_quantity import InvalidQuantityError, parse_cpu_cores, parse_memory_bytes
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


def _device_available(device: dict) -> tuple[int, int, int]:
    return (
        device["allocated_cpu"] - device["used_cpu"],
        device["allocated_memory_bytes"] - device["used_memory_bytes"],
        device["allocated_storage_bytes"] - device["used_storage_bytes"],
    )


async def _release_device_resources(container: dict) -> None:
    '''
    P12 (see ~/browseterm/p.md's "P12" section): plan section 9 - "On Hibernate/Delete: decrement
    cached used resources." Only the Delete half is wired up here (see delete_container); a
    container's device_id/limits may be absent on legacy rows or malformed, in which case this is
    a best-effort no-op - a failure to release a cached counter does not fail the caller's delete,
    and P14's periodic reconciliation against real Kubernetes state is the actual backstop for any
    drift this leaves behind, not this function.
    '''
    device_id = container.get("device_id")
    if not device_id:
        return
    try:
        cpu = parse_cpu_cores(container["cpu_limit"])
        memory = parse_memory_bytes(container["memory_limit"])
        storage = parse_memory_bytes(container["storage_limit"])
    except (InvalidQuantityError, KeyError, TypeError):
        logger.error("could not parse container resource limits for release", extra={"container_id": container.get("id")})
        return

    device_ops = DeviceOps(DB_CONFIG)
    device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": container.get("user_id")})
    if not device_result.data:
        return
    device = device_result.data
    release_result = await asyncio.to_thread(
        device_ops.update,
        {"id": device_id, "user_id": container.get("user_id")},
        {
            "used_cpu": max(0, device["used_cpu"] - cpu),
            "used_memory_bytes": max(0, device["used_memory_bytes"] - memory),
            "used_storage_bytes": max(0, device["used_storage_bytes"] - storage),
        },
    )
    if not release_result.success:
        logger.error("device resource release failed", extra={"error": release_result.error, "device_id": device_id})


async def create_container(request: Request) -> JSONResponse:
    '''
    POST /containers - body must include user_id (Local-trusted, not client-trusted). device_id is
    optional - see P13 below.

    P12: validates the device belongs to the caller and is ACTIVE, validates requested
    cpu/memory/storage against that device's available (allocated - used) capacity, and reserves
    usage against the device BEFORE creating the container row - matching the plan's own
    section-22 bullet order for this task: "validate device, validate resources, reserve usage,
    create global container row, fail/release reservation paths". If the container row fails to
    create after usage was reserved, the reservation is released back.

    P13 (see ~/browseterm/p.md's "P13" section): device_id may be omitted, in which case the
    caller's currently-ACTIVE device is resolved automatically. browseterm-server-local (a
    per-user-Mac process) has no established way to learn "its own" device_id today - device
    registration/bootstrap is a Desktop-app concept (P07's device-bootstrap flow), a separate
    process Local has no IPC channel to. Cloud already enforces "at most one ACTIVE device per
    user at a time" everywhere else (device_handlers.py's _demote_other_devices), so resolving it
    the same way here - rather than inventing a new device-selection mechanism for Local - is
    consistent with that existing invariant, not a new one.
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        body = await request.json()
        user_id = body.get("user_id")
        name = body.get("name")
        device_id = body.get("device_id")
        cpu_limit = body.get("cpu_limit")
        memory_limit = body.get("memory_limit")
        storage_limit = body.get("storage_limit")
        missing = [
            field for field, value in (
                ("user_id", user_id), ("name", name),
                ("cpu_limit", cpu_limit), ("memory_limit", memory_limit), ("storage_limit", storage_limit),
            ) if not value
        ]
        if missing:
            return JSONResponse(content={"error": f"{', '.join(missing)} required"}, status_code=400)

        try:
            requested_cpu = parse_cpu_cores(cpu_limit)
            requested_memory = parse_memory_bytes(memory_limit)
            requested_storage = parse_memory_bytes(storage_limit)
        except InvalidQuantityError as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"name": name, "user_id": user_id})
        if existing.data:
            return JSONResponse(
                content={"error": f"Container with name '{name}' already exists for this user."},
                status_code=409,
            )

        device_ops = DeviceOps(DB_CONFIG)
        if device_id:
            device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
            if not device_result.data:
                return JSONResponse(content={"error": "Device not found"}, status_code=404)
            device = device_result.data
            if device["status"] != DeviceStatus.ACTIVE.value:
                return JSONResponse(content={"error": "Device is not active"}, status_code=400)
        else:
            # P13: no device_id supplied - resolve the caller's currently-ACTIVE device.
            active_result = await asyncio.to_thread(
                device_ops.find_one, {"user_id": user_id, "status": DeviceStatus.ACTIVE}
            )
            if not active_result.data:
                return JSONResponse(
                    content={"error": "No active device registered for this user"}, status_code=400
                )
            device = active_result.data
            device_id = device["id"]

        available_cpu, available_memory, available_storage = _device_available(device)
        resource_errors = []
        if requested_cpu > available_cpu:
            resource_errors.append("cpu_limit exceeds this device's available capacity")
        if requested_memory > available_memory:
            resource_errors.append("memory_limit exceeds this device's available capacity")
        if requested_storage > available_storage:
            resource_errors.append("storage_limit exceeds this device's available capacity")
        if resource_errors:
            return JSONResponse(content={"error": resource_errors}, status_code=400)

        # Reserve usage before creating the row (see docstring for why this ordering).
        reserve_result = await asyncio.to_thread(
            device_ops.update,
            {"id": device_id, "user_id": user_id},
            {
                "used_cpu": device["used_cpu"] + requested_cpu,
                "used_memory_bytes": device["used_memory_bytes"] + requested_memory,
                "used_storage_bytes": device["used_storage_bytes"] + requested_storage,
            },
        )
        if not reserve_result.success:
            logger.error("resource reservation failed", extra={"error": reserve_result.error})
            return JSONResponse(content={"error": "Error reserving device resources"}, status_code=500)

        # device_id explicitly re-set here, not just relying on whatever body.items() carries -
        # it may have been auto-resolved above rather than supplied by the caller at all.
        insert_data = {k: v for k, v in body.items() if k != "id"}
        insert_data["device_id"] = device_id
        result = await asyncio.to_thread(ops.insert, insert_data)
        if not result.success:
            logger.error("container create failed", extra={"error": result.error})
            # Fail/release path: the row never got created, give the reservation back.
            await asyncio.to_thread(
                device_ops.update,
                {"id": device_id, "user_id": user_id},
                {
                    "used_cpu": device["used_cpu"],
                    "used_memory_bytes": device["used_memory_bytes"],
                    "used_storage_bytes": device["used_storage_bytes"],
                },
            )
            return JSONResponse(content={"error": "Error creating container"}, status_code=500)
        return JSONResponse(content={"container": result.data}, status_code=201)
    except Exception:
        logger.error("container create failed", exc_info=True)
        return JSONResponse(content={"error": "Error creating container"}, status_code=500)


async def resume_container(request: Request) -> JSONResponse:
    '''
    POST /containers/{container_id}/resume - body must include user_id (Local-trusted).
    device_id is optional, same auto-resolve-to-active-device pattern as create_container (P13).

    P19 (see ~/browseterm/p.md's "P19" section, plan section 15): the cross-device resume
    transition. Only a `HIBERNATED` container can resume - enforced via a conditional (CAS)
    update (`expected_status=HIBERNATED`, same pattern P09's `update_container_status`
    established): the UPDATE's own WHERE clause only matches a row that's still `HIBERNATED` at
    the instant it runs, and Postgres serializes concurrent UPDATEs to the same row, so two
    concurrent resume attempts for the same container can never both win - this is the plan's
    "Cloud checks container not active elsewhere" / "only one active mutable runtime per
    workspace in V1". `ContainerOps.update()` reports success even when zero rows matched (the
    same "filter didn't match = success, not error" semantic P09 preserves elsewhere), so the
    actual outcome is confirmed by re-reading the row afterward, not by trusting `.success` alone.

    Validates/reserves the resuming device's capacity using the container's own already-stored
    resource limits (resume never changes a container's size, so nothing new is requested) -
    same reserve-then-write ordering and release-on-failure safety net as create_container.

    Local performs the actual ContainerMaker pod start after this returns 200; on a pod-start
    failure, Local is expected to call the existing `POST /containers/{id}/hibernate` (P18) to
    roll back - that already does exactly the right thing (clears device_id, releases the
    reservation, sets HIBERNATED), so no separate rollback endpoint is needed here.
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            return JSONResponse(content={"error": "user_id is required"}, status_code=400)
        device_id = body.get("device_id")

        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        if not existing.data:
            return _not_found()
        container = existing.data
        if container["status"] != ContainerStatus.HIBERNATED.value:
            return JSONResponse(content={"error": "Container is not hibernated"}, status_code=409)

        try:
            requested_cpu = parse_cpu_cores(container["cpu_limit"])
            requested_memory = parse_memory_bytes(container["memory_limit"])
            requested_storage = parse_memory_bytes(container["storage_limit"])
        except InvalidQuantityError as e:
            return JSONResponse(content={"error": str(e)}, status_code=400)

        device_ops = DeviceOps(DB_CONFIG)
        if device_id:
            device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": user_id})
            if not device_result.data:
                return JSONResponse(content={"error": "Device not found"}, status_code=404)
            device = device_result.data
            if device["status"] != DeviceStatus.ACTIVE.value:
                return JSONResponse(content={"error": "Device is not active"}, status_code=400)
        else:
            active_result = await asyncio.to_thread(
                device_ops.find_one, {"user_id": user_id, "status": DeviceStatus.ACTIVE}
            )
            if not active_result.data:
                return JSONResponse(
                    content={"error": "No active device registered for this user"}, status_code=400
                )
            device = active_result.data
            device_id = device["id"]

        available_cpu, available_memory, available_storage = _device_available(device)
        resource_errors = []
        if requested_cpu > available_cpu:
            resource_errors.append("cpu_limit exceeds this device's available capacity")
        if requested_memory > available_memory:
            resource_errors.append("memory_limit exceeds this device's available capacity")
        if requested_storage > available_storage:
            resource_errors.append("storage_limit exceeds this device's available capacity")
        if resource_errors:
            return JSONResponse(content={"error": resource_errors}, status_code=400)

        # Reserve usage before the CAS transition (see docstring for why this ordering).
        reserve_result = await asyncio.to_thread(
            device_ops.update,
            {"id": device_id, "user_id": user_id},
            {
                "used_cpu": device["used_cpu"] + requested_cpu,
                "used_memory_bytes": device["used_memory_bytes"] + requested_memory,
                "used_storage_bytes": device["used_storage_bytes"] + requested_storage,
            },
        )
        if not reserve_result.success:
            logger.error("resource reservation failed", extra={"error": reserve_result.error})
            return JSONResponse(content={"error": "Error reserving device resources"}, status_code=500)

        async def _release_reservation() -> None:
            await asyncio.to_thread(
                device_ops.update,
                {"id": device_id, "user_id": user_id},
                {
                    "used_cpu": device["used_cpu"],
                    "used_memory_bytes": device["used_memory_bytes"],
                    "used_storage_bytes": device["used_storage_bytes"],
                },
            )

        cas_result = await asyncio.to_thread(
            ops.update,
            {"id": container_id, "user_id": user_id, "status": ContainerStatus.HIBERNATED},
            {"device_id": device_id, "status": ContainerStatus.RESUMING},
        )
        if not cas_result.success:
            logger.error("resume update failed", extra={"error": cas_result.error})
            await _release_reservation()
            return JSONResponse(content={"error": "Error resuming container"}, status_code=500)

        updated = await asyncio.to_thread(ops.find_one, {"id": container_id, "user_id": user_id})
        if (
            not updated.data
            or updated.data["status"] != ContainerStatus.RESUMING.value
            or updated.data["device_id"] != device_id
        ):
            # Lost the CAS race - some other request already resumed/changed this container
            # first. Give the reservation back; the caller never got a runtime out of this.
            await _release_reservation()
            return JSONResponse(content={"error": "Container is not hibernated"}, status_code=409)

        return JSONResponse(content={"container": updated.data})
    except Exception:
        logger.error("resume failed", exc_info=True)
        return JSONResponse(content={"error": "Error resuming container"}, status_code=500)


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
    '''
    POST /containers/{container_id}/delete - body must include user_id (Local-trusted).

    P12: releases the container's reserved device resources on successful delete (plan section 9:
    "On Hibernate/Delete: decrement cached used resources" - only the Delete half; see
    _release_device_resources's docstring for why Hibernate's release isn't wired up here too).
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

        result = await asyncio.to_thread(ops.delete, {"id": container_id, "user_id": user_id})
        if not result.success:
            logger.error("container delete failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error deleting container"}, status_code=500)

        await _release_device_resources(existing.data)
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


async def list_idle_containers(request: Request) -> JSONResponse:
    '''
    GET /internal/devices/{device_id}/containers/idle?idle_threshold_seconds=N

    P18 (see ~/browseterm/p.md's "P18" section, plan section 16) - `reaper` (browseterm_workload)
    uses this to find its own device's RUNNING-but-idle containers instead of querying Postgres
    directly. Same trusted-SYSTEM-caller pattern as P09/P14 (no user_id) - device_id is the
    scoping key here, not user_id, matching the plan's explicit instruction that the reaper "must
    operate only on containers whose device_id is the current device."
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        device_id = request.path_params["device_id"]
        idle_threshold_seconds = request.query_params.get("idle_threshold_seconds")
        if not idle_threshold_seconds:
            return JSONResponse(content={"error": "idle_threshold_seconds is required"}, status_code=400)
        try:
            idle_threshold_seconds = int(idle_threshold_seconds)
        except ValueError:
            return JSONResponse(content={"error": "idle_threshold_seconds must be an integer"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        result = await asyncio.to_thread(ops.find_idle_containers, idle_threshold_seconds, device_id)
        if not result.success:
            logger.error("list idle containers failed", extra={"error": result.error})
            return JSONResponse(content={"error": "Error listing idle containers"}, status_code=500)
        return JSONResponse(content={"containers": result.data})
    except Exception:
        logger.error("list idle containers failed", exc_info=True)
        return JSONResponse(content={"error": "Error listing idle containers"}, status_code=500)


async def hibernate_container(request: Request) -> JSONResponse:
    '''
    POST /internal/containers/{container_id}/hibernate

    P18: the compound hibernate transition (plan section 14) - "After successful hibernate:
    device_id = NULL, release device usage." Same trusted-SYSTEM-caller pattern as the routes
    above; `reaper` calls this only AFTER it has itself confirmed (via the save-status polling
    it already does against the user-scoped container API, whose user_id it already knows from
    the row `list_idle_containers` returned) that the save this hibernate is based on actually
    succeeded - this endpoint has no save-confirmation logic of its own, it only performs the
    state transition once the caller has already decided it's safe to.

    Sets status=HIBERNATED and device_id=NULL, then releases the container's device resource
    reservation (reusing `_release_device_resources`, same helper `delete_container` uses) based
    on the container's device_id/limits as they were BEFORE this update.
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        container_id = request.path_params["container_id"]
        ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(ops.find_one, {"id": container_id})
        if not existing.data:
            return _not_found()

        result = await asyncio.to_thread(
            ops.update, {"id": container_id}, {"status": ContainerStatus.HIBERNATED, "device_id": None}
        )
        if not result.success:
            logger.error("hibernate failed", extra={"container_id": container_id, "error": result.error})
            return JSONResponse(content={"error": "Error hibernating container"}, status_code=500)

        await _release_device_resources(existing.data)
        return JSONResponse(content={"ok": True})
    except Exception:
        logger.error("hibernate failed", exc_info=True)
        return JSONResponse(content={"error": "Error hibernating container"}, status_code=500)


async def reconcile_device_resources(request: Request) -> JSONResponse:
    '''
    POST /internal/devices/resources/reconcile

    P14 (see ~/browseterm/p.md's "P14" section): status_monitor (browseterm_workload) periodically
    reports the container_ids of pods it currently sees actually Running in real Kubernetes - the
    ground truth P12's cached used_cpu/used_memory_bytes/used_storage_bytes counters can drift
    away from (a missed release, a retried request, manual DB surgery). Same trusted SYSTEM caller
    as update_container_status - no user_id, status_monitor watches its whole local cluster.

    Body: {"running_container_ids": ["...", ...]}. For each id, looks up its container row (no
    user_id filter - same reasoning as update_container_status) and, for every container that has
    a device_id, sums its parsed cpu/memory/storage into a per-device running total. Each device
    with at least one running container this call reports gets its used_* fields OVERWRITTEN
    (not incremented) to that freshly-computed sum - this is a repair, not an adjustment.

    Known limitation, not handled by this call alone: a device whose containers have ALL stopped
    running since the last reconcile (nothing in running_container_ids references it any more) is
    not reset to zero here, since nothing in the request identifies it as needing reconciliation -
    see p.md's P14 section for why this is a deliberate v1 scope decision, not an oversight.
    '''
    if not _internal_auth_ok(request):
        return _unauthorized()
    try:
        body = await request.json()
        running_container_ids = body.get("running_container_ids")
        if not isinstance(running_container_ids, list):
            return JSONResponse(content={"error": "running_container_ids must be a list"}, status_code=400)

        ops = ContainerOps(DB_CONFIG)
        device_totals: dict[str, dict[str, int]] = {}
        for container_id in running_container_ids:
            result = await asyncio.to_thread(ops.find_one, {"id": container_id})
            container = result.data
            if not container or not container.get("device_id"):
                continue
            try:
                cpu = parse_cpu_cores(container["cpu_limit"])
                memory = parse_memory_bytes(container["memory_limit"])
                storage = parse_memory_bytes(container["storage_limit"])
            except (InvalidQuantityError, KeyError, TypeError):
                logger.error("could not parse container resource limits for reconcile", extra={"container_id": container_id})
                continue
            totals = device_totals.setdefault(
                container["device_id"], {"used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0}
            )
            totals["used_cpu"] += cpu
            totals["used_memory_bytes"] += memory
            totals["used_storage_bytes"] += storage

        device_ops = DeviceOps(DB_CONFIG)
        reconciled: dict[str, dict[str, int]] = {}
        for device_id, totals in device_totals.items():
            result = await asyncio.to_thread(device_ops.update, {"id": device_id}, totals)
            if not result.success:
                logger.error("device resource reconcile failed", extra={"error": result.error, "device_id": device_id})
                continue
            reconciled[device_id] = totals
        return JSONResponse(content={"reconciled_devices": reconciled})
    except Exception:
        logger.error("device resource reconcile failed", exc_info=True)
        return JSONResponse(content={"error": "Error reconciling device resources"}, status_code=500)


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
