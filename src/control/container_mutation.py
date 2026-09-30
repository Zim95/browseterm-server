'''
Container-field mutation from a terminal CommandResult (migration Parts 8-11). Deliberately
separate from src/control/servicer.py's generic command-row bookkeeping (Part 6) - what fields
change and how is operation-specific, this module is where that per-operation knowledge lives.

Every mutation goes through DeviceCommandOps.conditional_container_update (device_id +
placement_generation gated) so a stale/superseded command can never overwrite a newer placement -
the same invariant Part 1 built and Part 6's own CommandResult handling already checks before
calling into here.
'''
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from browseterm_db.models.containers import ContainerStatus
from browseterm_db.operations.all_operations import ContainerOps, DeviceOps, DeviceCommandOps

from src.cloud.config import DB_CONFIG
from src.cloud.resource_quantity import InvalidQuantityError, parse_cpu_cores, parse_memory_bytes
from src.common.logging_setup import get_logger

logger = get_logger("container_mutation")


async def apply_command_result(command: dict, status: str, result_json: Optional[str], error_message: Optional[str]) -> None:
    if not command.get("container_id"):
        return  # device-wide commands (none exist yet) have nothing to mutate
    operation = command["operation"]
    try:
        result = json.loads(result_json) if result_json else {}
    except (json.JSONDecodeError, ValueError):
        result = {}

    if operation == "Create":
        await _apply_create_or_resume(command, status, result)
    elif operation == "Delete":
        await _apply_delete(command, status)
    elif operation == "Hibernate":
        await _apply_hibernate(command, status, result)
    elif operation == "Resume":
        await _apply_create_or_resume(command, status, result)
    elif operation == "Save":
        await _apply_save(command, status, result, error_message)
    # Reconcile: Part 22, not mutating container fields here.


async def _apply_create_or_resume(command: dict, status: str, result: dict) -> None:
    command_ops = DeviceCommandOps(DB_CONFIG)
    if status == "succeeded":
        update_data = {
            "status": ContainerStatus.RUNNING,
            "kubernetes_id": result.get("kubernetes_id"),
            "ip_address": result.get("ip_address"),
            "associated_resources": result.get("associated_resources"),
        }
    else:
        # "If pod creation fails, release reservation and return to HIBERNATED when safe" (Part
        # 11) - for Create there's no prior HIBERNATED state to return to, so FAILED is the
        # honest terminal state instead (matches ContainerStatus's existing FAILED value).
        update_data = {"status": ContainerStatus.HIBERNATED if command["operation"] == "Resume" else ContainerStatus.FAILED}
    matched = await asyncio.to_thread(
        command_ops.conditional_container_update,
        command["container_id"], command["device_id"], command["placement_generation"], update_data,
    )
    if not matched.success or matched.data.get("matched", 0) == 0:
        logger.info("container mutation skipped (stale placement)", extra={"command_id": command["id"], "operation": command["operation"]})
        return

    if status == "succeeded":
        # Move this container's resources from reserved_* (already released above, via
        # release_quota_for_command in servicer.py) into used_* - confirmed-running capacity now
        # genuinely reflects a real pod. Without this, used_* only ever changes via
        # status_monitor's resource_reconciler.py, which runs on a slow, drift-repair-only cadence
        # (RECONCILE_INTERVAL_SECONDS, 300s by default) - a real bug caught live: a container's
        # pod was genuinely up and consuming real device capacity, but the device's own used_cpu/
        # used_memory_bytes/used_storage_bytes stayed at their pre-create values for up to 5
        # minutes, so a second create request saw stale "available" capacity as if the first
        # container didn't exist yet.
        container_ops = ContainerOps(DB_CONFIG)
        existing = await asyncio.to_thread(container_ops.find_one, {"id": command["container_id"], "user_id": command["user_id"]})
        if existing.data:
            await _apply_used_resources(existing.data, DeviceOps(DB_CONFIG))


async def _apply_used_resources(container: dict, device_ops: DeviceOps) -> None:
    '''The increment counterpart to _release_used_resources below - moves a container's own
    resource limits into devices.used_* once its pod is confirmed Running.'''
    device_id = container.get("device_id")
    if not device_id:
        return
    try:
        cpu = parse_cpu_cores(container["cpu_limit"])
        memory = parse_memory_bytes(container["memory_limit"])
        storage = parse_memory_bytes(container["storage_limit"])
    except (InvalidQuantityError, KeyError, TypeError):
        logger.error("could not parse container resource limits to apply used capacity", extra={"container_id": container.get("id")})
        return

    device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": container.get("user_id")})
    if not device_result.data:
        return
    device = device_result.data
    await asyncio.to_thread(
        device_ops.update,
        {"id": device_id, "user_id": container.get("user_id")},
        {
            "used_cpu": device["used_cpu"] + cpu,
            "used_memory_bytes": device["used_memory_bytes"] + memory,
            "used_storage_bytes": device["used_storage_bytes"] + storage,
        },
    )


async def _apply_delete(command: dict, status: str) -> None:
    if status != "succeeded":
        # "Missing pod/service is success" already makes delete.py's handler report SUCCEEDED
        # for an already-gone pod - a real FAILED here means something else went wrong.
        #
        # The container row is never soft-deleted at request time (container_handlers.py's
        # _delete_container_via_device_command only flips status to DELETING) - it stays visible
        # to the user, rendered as an in-flight state, for exactly as long as the real teardown
        # takes. So a confirmed failure here must undo the optimistic DELETING status back to
        # RUNNING, the same "undo the optimistic transition on a confirmed failure" pattern
        # _apply_hibernate uses for its own HIBERNATING status - otherwise the container would be
        # stuck showing as permanently "still working" with a real, orphaned pod still running and
        # no way for anyone to see or retry it. Gated by conditional_container_update (device_id +
        # placement_generation) so a stale/superseded result can't clobber a newer placement.
        command_ops = DeviceCommandOps(DB_CONFIG)
        reverted = await asyncio.to_thread(
            command_ops.conditional_container_update,
            command["container_id"], command["device_id"], command["placement_generation"],
            {"status": ContainerStatus.RUNNING},
        )
        if not reverted.success or reverted.data.get("matched", 0) == 0:
            logger.info(
                "delete failure revert skipped (stale placement or already moved on)",
                extra={"command_id": command["id"], "container_id": command["container_id"]},
            )
        return

    container_ops = ContainerOps(DB_CONFIG)
    device_ops = DeviceOps(DB_CONFIG)
    existing = await asyncio.to_thread(container_ops.find_one, {"id": command["container_id"], "user_id": command["user_id"]})
    if not existing.data:
        return  # already gone (e.g. a duplicate result for an already-processed delete)

    await _release_unreleased_command_quota(command["container_id"])
    # Release used_* resources BEFORE the row itself is hard-deleted (and thus vanishes from the
    # UI): the owner explicitly asked for the entry to only leave the list once the pod is gone
    # AND its resources are released, not before. Releasing first means the worst case of a crash
    # between these two calls is a lingering-but-already-freed row, never a vanished row with
    # resources still shown as reserved.
    await _release_used_resources(existing.data, device_ops)
    delete_result = await asyncio.to_thread(container_ops.delete, {"id": command["container_id"], "user_id": command["user_id"]})
    if not delete_result.success:
        logger.error("container row delete failed after successful device delete", extra={"command_id": command["id"]})
        return


async def _apply_hibernate(command: dict, status: str, result: dict) -> None:
    command_ops = DeviceCommandOps(DB_CONFIG)
    if status != "succeeded":
        # The pod is genuinely still running (see hibernate.py's own POD_DELETE_FAILED_AFTER_SAVE
        # note - a real failure here never deletes the pod), but the container's own status was
        # already optimistically flipped to HIBERNATING the instant this command was created
        # (_hibernate_container_via_device_command) - nothing reverts that on failure, so the
        # container got stuck in HIBERNATING forever (an endless loading spinner in the UI, no
        # controls, no way to retry) even though the real pod was fine the whole time. Caught
        # live in production the same day HIBERNATE was first enabled: a real snapshot failure
        # (container-maker's REPO_NAME/REPO_PASSWORD not configured) left a container stranded
        # exactly this way. Revert to RUNNING, the same "undo the optimistic transition on a
        # confirmed failure" pattern _apply_delete already uses for its own soft-delete.
        reverted = await asyncio.to_thread(
            command_ops.conditional_container_update,
            command["container_id"], command["device_id"], command["placement_generation"],
            {"status": ContainerStatus.RUNNING},
        )
        if not reverted.success or reverted.data.get("matched", 0) == 0:
            logger.info(
                "hibernate failure revert skipped (stale placement or already moved on)",
                extra={"command_id": command["id"], "container_id": command["container_id"]},
            )
        return

    container_ops = ContainerOps(DB_CONFIG)
    existing = await asyncio.to_thread(container_ops.find_one, {"id": command["container_id"], "user_id": command["user_id"]})

    # qa.md item 3: a skip_save (manual/UI) hibernate reports no saved_image at all - must NOT
    # overwrite whatever saved_image the container already had (e.g. from an earlier explicit
    # Save) with None. Only Reaper's save-then-delete path (or manual Save beforehand) ever sets
    # this field.
    update_data = {"status": ContainerStatus.HIBERNATED, "device_id": None}
    if result.get("saved_image"):
        update_data["saved_image"] = result["saved_image"]
    matched = await asyncio.to_thread(
        command_ops.conditional_container_update,
        command["container_id"], command["device_id"], command["placement_generation"],
        update_data,
    )
    if matched.success and matched.data.get("matched", 0) > 0 and existing.data:
        await _release_used_resources(existing.data, DeviceOps(DB_CONFIG))
        # HIBERNATE itself never reserves quota (only CREATE/RESUME do), but an *earlier*
        # CREATE/RESUME command for this same container may have reached a terminal status
        # without its reservation ever being released (a lost CommandResult, or a status
        # corrected by hand outside release_quota_for_command) - unlike delete_container, this
        # row survives hibernate (the container isn't removed, so no CASCADE risk), but it would
        # otherwise sit stranded for as long as the container stays hibernated. Sweep it here too.
        await _release_unreleased_command_quota(command["container_id"])


async def _apply_save(command: dict, status: str, result: dict, error_message: Optional[str]) -> None:
    '''SAVE never changes placement/device_id/status - the container stays RUNNING throughout,
    unlike HIBERNATE. snapshot_handlers.py::report_snapshot_result is the authoritative
    completion signal WHEN a snapshot Job actually got created - this is a redundant-but-harmless
    confirmation of the same saved_image on a successful CommandResult.

    But a SAVE can also fail before any Job exists at all - e.g. Container Maker's own RPC
    throwing on pod resolution (a real incident: "Cannot uniquely resolve the pod ... N pods
    share label") - a case report_snapshot_result never runs for, since there is no snapshot_job
    to call it. Left unhandled, containers.save_status silently keeps whatever it was from the
    container's last *successful* save, no save_status_change SSE event ever fires, and the
    frontend's Save button - which only re-enables on that SSE event (terminalpage.js's own
    updateSaveButtonState) - stays stuck on "Saving..." forever, with no way for the user to even
    see that the attempt failed. So a failed/timed-out command result gets the same conditional
    (device_id + placement_generation gated) treatment as success, just writing save_status/
    save_error instead of saved_image.'''
    command_ops = DeviceCommandOps(DB_CONFIG)
    if status != "succeeded":
        await asyncio.to_thread(
            command_ops.conditional_container_update,
            command["container_id"], command["device_id"], command["placement_generation"],
            {"save_status": "Failed", "save_error": (error_message or "")[:1000] or None},
        )
        return
    await asyncio.to_thread(
        command_ops.conditional_container_update,
        command["container_id"], command["device_id"], command["placement_generation"],
        {"saved_image": result.get("saved_image")},
    )


async def _release_unreleased_command_quota(container_id: str) -> None:
    '''Mirrors container_handlers.py's own _release_unreleased_command_quota - duplicated rather
    than imported to avoid a control -> cloud module dependency, same as _release_used_resources
    below. See that copy's docstring for why this must run before a container row is deleted: a
    CREATE/RESUME command's reserved quota is only ever released by a terminal CommandResult, and
    ON DELETE CASCADE would otherwise remove the only row it could ever be released against,
    stranding devices.reserved_* permanently.'''
    command_ops = DeviceCommandOps(DB_CONFIG)
    existing_commands = await asyncio.to_thread(command_ops.find, {"container_id": container_id})
    if not existing_commands.success:
        return
    for command in existing_commands.data or []:
        if command.get("quota_reserved_cpu") is not None and command.get("quota_released_at") is None:
            await asyncio.to_thread(command_ops.release_quota_for_command, command["id"])


async def _release_used_resources(container: dict, device_ops: DeviceOps) -> None:
    '''Mirrors container_handlers.py's own _release_device_resources - duplicated rather than
    imported to avoid a control -> cloud module dependency; kept deliberately small and identical
    in behavior. A real shared-util extraction is reasonable future cleanup, not required here.'''
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

    device_result = await asyncio.to_thread(device_ops.find_one, {"id": device_id, "user_id": container.get("user_id")})
    if not device_result.data:
        return
    device = device_result.data
    await asyncio.to_thread(
        device_ops.update,
        {"id": device_id, "user_id": container.get("user_id")},
        {
            "used_cpu": max(0, device["used_cpu"] - cpu),
            "used_memory_bytes": max(0, device["used_memory_bytes"] - memory),
            "used_storage_bytes": max(0, device["used_storage_bytes"] - storage),
        },
    )
