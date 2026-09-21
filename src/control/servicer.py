'''
The Cloud side of the Device Control bidirectional stream (BROWSETERM_CLOUD_CONTROL_PLANE_MIGRATION.md
Part 6). One Connect() call per Device Agent connection; runs for the lifetime of that TCP stream.

Container-field mutation (updating containers.status/kubernetes_id/etc from a CommandResult) is
deliberately NOT done here - which fields change and how is operation-specific (Create sets
kubernetes_id/ip_address, Hibernate clears device_id, ...) and belongs to Parts 8-11 as each
lifecycle operation is migrated. This part persists the command row itself (status/result/error/
timestamps), releases quota exactly once, and redelivers unfinished commands - the generic
envelope every operation shares.
'''
import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, List, Optional

import grpc
from sqlalchemy import text

from browseterm_db.operations.all_operations import DeviceCommandOps
from browseterm_db.models.device_commands import CommandStatus

from device_control_spec import device_control_pb2_grpc
from device_control_spec.device_control_pb2 import DeviceToCloud, CloudToDevice
from device_control_spec.device_control_types_pb2 import (
    HelloAccepted, ExecuteCommand, Ping, CommandStatus as WireCommandStatus,
    COMMAND_OPERATION_CREATE, COMMAND_OPERATION_DELETE, COMMAND_OPERATION_HIBERNATE,
    COMMAND_OPERATION_RESUME, COMMAND_OPERATION_RECONCILE,
)

from src.cloud.config import DB_CONFIG
from src.control.auth import authenticate_stream
from src.control.config import MINIMUM_AGENT_PROTOCOL_VERSION, PING_INTERVAL_SECONDS
from src.control.connection_registry import connection_registry, CHECK_PENDING_SENTINEL, ConnectionState
from src.control.container_mutation import apply_command_result
from src.common.logging_setup import get_logger

logger = get_logger("device_control_servicer")

# CommandResult.status on the wire only ever carries a terminal outcome.
_WIRE_STATUS_TO_MODEL = {
    WireCommandStatus.COMMAND_STATUS_SUCCEEDED: CommandStatus.SUCCEEDED,
    WireCommandStatus.COMMAND_STATUS_FAILED: CommandStatus.FAILED,
}


def _bump_connection_generation(device_id: str) -> None:
    '''Single atomic UPDATE (not read-then-write) - observability/diagnostic mirror of the
    in-memory ConnectionRegistry's own generation counter, which is the real routing authority
    for this single-replica deployment (see connection_registry.py's module docstring).'''
    session = DB_CONFIG.get_db_session()
    try:
        session.execute(
            text("UPDATE devices SET connection_generation = connection_generation + 1, "
                 "last_seen_at = :now, updated_at = :now WHERE id = :device_id"),
            {"device_id": device_id, "now": datetime.now(timezone.utc)},
        )
        session.commit()
    finally:
        session.close()


class DeviceControlServicer(device_control_pb2_grpc.DeviceControlServicer):

    async def Connect(self, request_iterator: AsyncIterator[DeviceToCloud], context: grpc.aio.ServicerContext):
        auth = await authenticate_stream(context)
        if not auth:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid or revoked device credential")
            return

        try:
            first_message = await request_iterator.__anext__()
        except StopAsyncIteration:
            return
        if first_message.WhichOneof("payload") != "hello":
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "first message on the stream must be Hello")
            return

        hello = first_message.hello
        if hello.device_id and hello.device_id != auth.device_id:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "Hello.device_id does not match the authenticated device")
            return
        if hello.protocol_version and hello.protocol_version < MINIMUM_AGENT_PROTOCOL_VERSION:
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"agent protocol version {hello.protocol_version!r} is below the minimum "
                f"supported {MINIMUM_AGENT_PROTOCOL_VERSION!r} - upgrade the Device Agent",
            )
            return

        device_id = auth.device_id
        user_id = auth.user_id
        state: ConnectionState = connection_registry.register(device_id, user_id)
        await asyncio.to_thread(_bump_connection_generation, device_id)
        logger.info("device.connected", extra={"device_id": device_id, "user_id": user_id, "generation": state.generation})

        reader_task = asyncio.create_task(self._read_loop(request_iterator, device_id, state))
        pinger_task = asyncio.create_task(self._pinger_loop(state))

        try:
            yield CloudToDevice(hello_accepted=HelloAccepted(
                connection_id=str(uuid.uuid4()),
                connection_generation=state.generation,
                minimum_agent_version=MINIMUM_AGENT_PROTOCOL_VERSION,
                reconciliation_required=True,
            ))

            # "After reconnect/Hello, query and redeliver unfinished commands."
            for execute_command in await self._pending_commands_as_execute(device_id):
                yield CloudToDevice(execute_command=execute_command)

            while not state.superseded:
                item = await state.queue.get()
                if item is CHECK_PENDING_SENTINEL:
                    for execute_command in await self._pending_commands_as_execute(device_id):
                        yield CloudToDevice(execute_command=execute_command)
                    continue
                yield item
        except asyncio.CancelledError:
            pass
        finally:
            reader_task.cancel()
            pinger_task.cancel()
            connection_registry.unregister(device_id, state.generation)
            logger.info("device.disconnected", extra={"device_id": device_id, "generation": state.generation})

    async def _pinger_loop(self, state: ConnectionState) -> None:
        try:
            while not state.superseded:
                await asyncio.sleep(PING_INTERVAL_SECONDS)
                if state.superseded:
                    return
                await state.queue.put(CloudToDevice(ping=Ping(sent_at_unix_ms=int(time.time() * 1000))))
        except asyncio.CancelledError:
            pass

    async def _pending_commands_as_execute(self, device_id: str) -> List[ExecuteCommand]:
        command_ops = DeviceCommandOps(DB_CONFIG)
        result = await asyncio.to_thread(command_ops.find_pending_for_device, device_id)
        if not result.success:
            logger.error("failed to query pending commands", extra={"device_id": device_id, "error": result.error})
            return []

        execute_commands: List[ExecuteCommand] = []
        for command in result.data:
            # QUEUED -> DELIVERED (or re-stamped if already DELIVERED - redelivery is expected
            # and safe). ACCEPTED/RUNNING commands are also redelivered as-is on reconnect so the
            # device can decide whether it already finished the work (idempotent by command_id).
            if command["status"] == CommandStatus.QUEUED.value:
                await asyncio.to_thread(
                    command_ops.update,
                    {"id": command["id"], "device_id": device_id},
                    {"status": CommandStatus.DELIVERED, "delivered_at": datetime.now(timezone.utc),
                     "attempt_count": command["attempt_count"] + 1},
                )
            operation_enum = _operation_to_wire(command["operation"])
            if operation_enum is None:
                continue
            execute_commands.append(ExecuteCommand(
                command_id=command["id"],
                operation=operation_enum,
                container_id=command["container_id"] or "",
                device_id=device_id,
                placement_generation=command["placement_generation"],
                expected_container_state=command["expected_container_state"] or "",
                trace_id=command["correlation_id"] or command["request_id"] or "",
                container_config_json=command.get("container_config_json") or "",
            ))
        return execute_commands

    async def _read_loop(self, request_iterator: AsyncIterator[DeviceToCloud], device_id: str, state: ConnectionState) -> None:
        try:
            async for message in request_iterator:
                connection_registry.touch(device_id, state.generation)
                kind = message.WhichOneof("payload")
                if kind == "heartbeat":
                    continue  # touch() above already recorded the activity
                elif kind == "command_accepted":
                    await self._handle_command_accepted(device_id, message.command_accepted)
                elif kind == "command_progress":
                    await self._handle_command_progress(device_id, message.command_progress)
                elif kind == "command_result":
                    await self._handle_command_result(device_id, message.command_result)
                elif kind == "pong":
                    pass
                # inventory_report / terminal_tunnel_registration / local_event: reconciliation
                # (Part 22) and tunnel cutover (Part 13) - intentionally not handled yet here.
        except asyncio.CancelledError:
            pass
        except grpc.aio.AioRpcError:
            pass  # stream closed from the other side; Connect()'s own cleanup handles the rest

    async def _handle_command_accepted(self, device_id: str, accepted) -> None:
        command_ops = DeviceCommandOps(DB_CONFIG)
        await asyncio.to_thread(
            command_ops.update,
            {"id": accepted.command_id, "device_id": device_id},
            {"status": CommandStatus.ACCEPTED, "accepted_at": datetime.now(timezone.utc)},
        )

    async def _handle_command_progress(self, device_id: str, progress) -> None:
        command_ops = DeviceCommandOps(DB_CONFIG)
        await asyncio.to_thread(
            command_ops.update,
            {"id": progress.command_id, "device_id": device_id},
            {
                "status": CommandStatus.RUNNING,
                "started_at": datetime.now(timezone.utc),
                "progress_stage": progress.progress_stage or None,
                "progress_message": (progress.progress_message or "")[:500] or None,
            },
        )

    async def _handle_command_result(self, device_id: str, result) -> None:
        command_ops = DeviceCommandOps(DB_CONFIG)
        model_status = _WIRE_STATUS_TO_MODEL.get(result.status)
        if model_status is None:
            logger.error("command_result with non-terminal status ignored", extra={"command_id": result.command_id})
            return

        existing = await asyncio.to_thread(command_ops.find_one, {"id": result.command_id, "device_id": device_id})
        if not existing.data:
            logger.info("command_result for unknown/foreign command ignored", extra={"command_id": result.command_id, "device_id": device_id})
            return
        if existing.data["placement_generation"] != result.placement_generation:
            # "Old device result rejected" / "stale device/generation result rejected" - a result
            # from a placement generation the container has since moved past.
            logger.info(
                "stale command_result rejected", extra={
                    "command_id": result.command_id, "device_id": device_id,
                    "result_generation": result.placement_generation,
                    "current_generation": existing.data["placement_generation"],
                },
            )
            return
        if existing.data["status"] in (CommandStatus.SUCCEEDED.value, CommandStatus.FAILED.value, CommandStatus.CANCELLED.value):
            return  # duplicate delivery is expected and safe - already terminal, no-op

        await asyncio.to_thread(
            command_ops.update,
            {"id": result.command_id, "device_id": device_id},
            {
                "status": model_status,
                "completed_at": datetime.now(timezone.utc),
                "result": result.result_json or None,
                "error_code": result.error_code or None,
                "error_message": (result.error_message or "")[:1000] or None,
            },
        )
        await asyncio.to_thread(command_ops.release_quota_for_command, result.command_id)
        await apply_command_result(
            existing.data, "succeeded" if model_status == CommandStatus.SUCCEEDED else "failed",
            result.result_json or None, result.error_message or None,
        )


_OPERATION_TO_WIRE = {
    "Create": COMMAND_OPERATION_CREATE,
    "Delete": COMMAND_OPERATION_DELETE,
    "Hibernate": COMMAND_OPERATION_HIBERNATE,
    "Resume": COMMAND_OPERATION_RESUME,
    "Reconcile": COMMAND_OPERATION_RECONCILE,
}


def _operation_to_wire(operation_value: str) -> Optional[int]:
    return _OPERATION_TO_WIRE.get(operation_value)
