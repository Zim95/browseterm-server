'''
Shared "apply a terminal CommandResult" logic (Parts 6/8-11), reusable from both the Device
Control gRPC stream (servicer.py) and the new HTTP result-reporting endpoint
(src/cloud/device_command_result_handlers.py).

Added 2026-09-26: Device Agent no longer has to rely solely on the long-lived Device Control
stream to report that a command finished. That stream has a documented, repeatedly-observed
reliability problem in this environment (Traefik's reverse-proxy times out reading the streaming
h2c response every ~30-90s - see BROWSETERM_MIGRATION_PROGRESS.md's own recurring notes on this),
so a CommandResult queued on it could take up to that long to actually reach Cloud - which is what
made a manual Hibernate/Delete look "stuck" even though the real pod-delete work had already
finished within seconds. Device Agent's OTHER synchronous calls (request_hibernate,
get_save_status) never had this problem, because they are short-lived HTTP request/response, not
a persistent stream - this module lets CommandResult reporting use that same reliable pattern,
without changing the actual safety ordering anywhere: Cloud still only marks a container
Hibernated/Deleted/Running once it receives a result confirming the real action (pod deleted, pod
created, save confirmed) actually happened - only the transport for reporting that changed.
'''
import asyncio
from datetime import datetime, timezone
from typing import Optional

from browseterm_db.operations.all_operations import DeviceCommandOps
from browseterm_db.models.device_commands import CommandStatus

from src.cloud.config import DB_CONFIG
from src.control.container_mutation import apply_command_result
from src.common.logging_setup import get_logger

logger = get_logger("command_result_ops")

_STATUS_TO_MODEL = {"succeeded": CommandStatus.SUCCEEDED, "failed": CommandStatus.FAILED}


async def apply_terminal_command_result(
    device_id: str, command_id: str, status: str, result_json: Optional[str],
    error_code: Optional[str], error_message: Optional[str], placement_generation: int,
) -> None:
    '''status is "succeeded" or "failed" (already normalized/lowercase - both callers translate
    their own wire/HTTP status representation to this before calling in).

    Idempotent/safe to call more than once for the same command_id - duplicate delivery is
    expected (a resend after a dropped ack, or the same result eventually arriving over both the
    stream and the HTTP path during Device Agent's rollout window).'''
    model_status = _STATUS_TO_MODEL.get(status)
    if model_status is None:
        logger.error("command_result with non-terminal status ignored", extra={"command_id": command_id, "status": status})
        return

    command_ops = DeviceCommandOps(DB_CONFIG)
    existing = await asyncio.to_thread(command_ops.find_one, {"id": command_id, "device_id": device_id})
    if not existing.data:
        logger.info("command_result for unknown/foreign command ignored", extra={"command_id": command_id, "device_id": device_id})
        return
    if existing.data["placement_generation"] != placement_generation:
        # "Old device result rejected" / "stale device/generation result rejected" - a result from
        # a placement generation the container has since moved past.
        logger.info(
            "stale command_result rejected", extra={
                "command_id": command_id, "device_id": device_id,
                "result_generation": placement_generation,
                "current_generation": existing.data["placement_generation"],
            },
        )
        return
    if existing.data["status"] in (CommandStatus.SUCCEEDED.value, CommandStatus.FAILED.value, CommandStatus.CANCELLED.value):
        return  # duplicate delivery is expected and safe - already terminal, no-op

    await asyncio.to_thread(
        command_ops.update,
        {"id": command_id, "device_id": device_id},
        {
            "status": model_status,
            "completed_at": datetime.now(timezone.utc),
            "result": result_json or None,
            "error_code": error_code or None,
            "error_message": (error_message or "")[:1000] or None,
        },
    )
    await asyncio.to_thread(command_ops.release_quota_for_command, command_id)
    await apply_command_result(
        existing.data, "succeeded" if model_status == CommandStatus.SUCCEEDED else "failed",
        result_json, error_message,
    )
