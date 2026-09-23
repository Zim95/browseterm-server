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
        await _apply_save(command, status, result)
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


async def _apply_delete(command: dict, status: str) -> None:
    if status != "succeeded":
        # "Missing pod/service is success" already makes delete.py's handler report SUCCEEDED
        # for an already-gone pod - a real FAILED here means something else went wrong.
        #
        # The container row was soft-deleted (deleted_at stamped) the instant DELETE was
        # requested, so it's already invisible to the user and its name already free for reuse -
        # a real failure here must undo that, or a container whose teardown genuinely failed
        # would vanish from the user's view forever with a real, orphaned pod still running and
        # no way for anyone to see or retry it. Reverting is best-effort: if a *different*
        # container has since claimed this name (a real possibility now that the name frees up
        # immediately), the partial unique index on (user_id, name) rejects the revert and this
        # container stays soft-deleted, permanently invisible - a genuine, rare edge case, not
        # silently corrected here; Part 22's reconciliation loop is the intended backstop for it.
        container_ops = ContainerOps(DB_CONFIG)
        revert_result = await asyncio.to_thread(
            container_ops.update, {"id": command["container_id"], "user_id": command["user_id"]}, {"deleted_at": None},
        )
        if not revert_result.success:
            logger.error(
                "could not un-soft-delete container after failed device delete - name likely reused already",
                extra={"command_id": command["id"], "container_id": command["container_id"], "error": revert_result.error},
            )
        return

    container_ops = ContainerOps(DB_CONFIG)
    device_ops = DeviceOps(DB_CONFIG)
    existing = await asyncio.to_thread(container_ops.find_one, {"id": command["container_id"], "user_id": command["user_id"]})
    if not existing.data:
        return  # already gone (e.g. a duplicate result for an already-processed delete)

    await _release_unreleased_command_quota(command["container_id"])
    delete_result = await asyncio.to_thread(container_ops.delete, {"id": command["container_id"], "user_id": command["user_id"]})
    if not delete_result.success:
        logger.error("container row delete failed after successful device delete", extra={"command_id": command["id"]})
        return

    await _release_used_resources(existing.data, device_ops)


async def _apply_hibernate(command: dict, status: str, result: dict) -> None:
    command_ops = DeviceCommandOps(DB_CONFIG)
    if status != "succeeded":
        return  # pod is still running (see hibernate.py's own POD_DELETE_FAILED_AFTER_SAVE note) - leave status as RUNNING, unchanged

    container_ops = ContainerOps(DB_CONFIG)
    existing = await asyncio.to_thread(container_ops.find_one, {"id": command["container_id"], "user_id": command["user_id"]})

    matched = await asyncio.to_thread(
        command_ops.conditional_container_update,
        command["container_id"], command["device_id"], command["placement_generation"],
        {"status": ContainerStatus.HIBERNATED, "device_id": None, "saved_image": result.get("saved_image")},
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


async def _apply_save(command: dict, status: str, result: dict) -> None:
    '''SAVE never changes placement/device_id/status - the container stays RUNNING throughout,
    unlike HIBERNATE. snapshot_handlers.py::report_snapshot_result already updates
    saved_image/save_status directly as snapshot_job's own report arrives (the authoritative
    completion signal); this is a redundant-but-harmless confirmation from Device Agent's own
    terminal CommandResult, applied the same conditional (device_id + placement_generation
    gated) way every other operation's result is, rather than skipped as a special case. On
    failure/timeout, leave the container row exactly as report_snapshot_result already left it -
    no separate "untouched" branch needed here, there is nothing new to apply.'''
    if status != "succeeded":
        return
    command_ops = DeviceCommandOps(DB_CONFIG)
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
