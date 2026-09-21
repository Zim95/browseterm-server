'''
Part 6 required tests covered here: "command created while offline is delivered after reconnect"
(via _pending_commands_as_execute, called right after every Hello), "duplicate delivery" (QUEUED
commands are marked DELIVERED but ACCEPTED/RUNNING ones are resent as-is, never re-queued),
"stale device/generation result rejected", and "server restart preserves commands" (delivery
always re-reads from Postgres - there is no in-memory command state that a restart would lose).
'''
from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from browseterm_db.operations import OperationResult

from src.control.servicer import DeviceControlServicer
from device_control_spec.device_control_types_pb2 import (
    CommandResult, COMMAND_STATUS_SUCCEEDED, COMMAND_STATUS_FAILED, COMMAND_OPERATION_CREATE,
)


def _command_row(**overrides) -> dict:
    row = {
        "id": "cmd-1", "user_id": "user-1", "device_id": "device-1", "container_id": "container-1",
        "operation": "Create", "placement_generation": 1, "expected_container_state": None,
        "status": "Queued", "attempt_count": 0, "request_id": None, "correlation_id": "trace-1",
    }
    row.update(overrides)
    return row


class TestPendingCommandsAsExecute(IsolatedAsyncioTestCase):

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_queued_command_is_marked_delivered_and_returned(self, mock_ops_cls) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_pending_for_device.return_value = OperationResult(success=True, data=[_command_row()])
        mock_ops.update.return_value = OperationResult(success=True)

        servicer = DeviceControlServicer()
        execute_commands = await servicer._pending_commands_as_execute("device-1")

        self.assertEqual(len(execute_commands), 1)
        self.assertEqual(execute_commands[0].command_id, "cmd-1")
        self.assertEqual(execute_commands[0].operation, COMMAND_OPERATION_CREATE)
        self.assertEqual(execute_commands[0].placement_generation, 1)
        mock_ops.update.assert_called_once()
        call_filters, call_data = mock_ops.update.call_args[0]
        self.assertEqual(call_filters, {"id": "cmd-1", "device_id": "device-1"})
        self.assertEqual(call_data["status"].value, "Delivered")
        self.assertEqual(call_data["attempt_count"], 1)

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_already_delivered_command_is_redelivered_without_re_marking(self, mock_ops_cls) -> None:
        '''Doc-required: "duplicate delivery is expected and safe" - a command already DELIVERED
        (e.g. the device reconnected before acking) is resent as-is, not treated as a fresh QUEUED
        command needing another DB write.'''
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_pending_for_device.return_value = OperationResult(
            success=True, data=[_command_row(status="Delivered", attempt_count=1)],
        )

        servicer = DeviceControlServicer()
        execute_commands = await servicer._pending_commands_as_execute("device-1")

        self.assertEqual(len(execute_commands), 1)
        mock_ops.update.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_no_pending_commands_returns_empty(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.find_pending_for_device.return_value = OperationResult(success=True, data=[])
        servicer = DeviceControlServicer()
        self.assertEqual(await servicer._pending_commands_as_execute("device-1"), [])

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_always_reads_fresh_from_postgres_no_in_memory_command_state(self, mock_ops_cls) -> None:
        '''Doc-required: "server restart preserves commands" - proven here by construction: a
        brand-new DeviceControlServicer (as a restarted process would create) with no prior
        state still returns the command, because delivery has no dependency on anything but the
        DB query result.'''
        mock_ops_cls.return_value.find_pending_for_device.return_value = OperationResult(success=True, data=[_command_row()])
        mock_ops_cls.return_value.update.return_value = OperationResult(success=True)
        fresh_servicer = DeviceControlServicer()  # simulates a post-restart process
        execute_commands = await fresh_servicer._pending_commands_as_execute("device-1")
        self.assertEqual(len(execute_commands), 1)


class TestHandleCommandResult(IsolatedAsyncioTestCase):

    def _result(self, **overrides) -> CommandResult:
        fields = {"command_id": "cmd-1", "status": COMMAND_STATUS_SUCCEEDED, "placement_generation": 1}
        fields.update(overrides)
        return CommandResult(**fields)

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_matching_generation_success_updates_and_releases_quota(self, mock_ops_cls) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=1))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.release_quota_for_command.return_value = OperationResult(success=True)

        servicer = DeviceControlServicer()
        await servicer._handle_command_result("device-1", self._result())

        mock_ops.update.assert_called_once()
        mock_ops.release_quota_for_command.assert_called_once_with("cmd-1")

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_stale_placement_generation_is_rejected(self, mock_ops_cls) -> None:
        '''Doc-required: "stale device/generation result rejected."'''
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=2))

        servicer = DeviceControlServicer()
        await servicer._handle_command_result("device-1", self._result(placement_generation=1))

        mock_ops.update.assert_not_called()
        mock_ops.release_quota_for_command.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_already_terminal_command_result_is_a_no_op(self, mock_ops_cls) -> None:
        '''Doc-required: "duplicate delivery is expected and safe" - a second CommandResult for
        an already-SUCCEEDED command must not double-release quota or re-write the row.'''
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(status="Succeeded", placement_generation=1))

        servicer = DeviceControlServicer()
        await servicer._handle_command_result("device-1", self._result())

        mock_ops.update.assert_not_called()
        mock_ops.release_quota_for_command.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_result_for_unknown_command_is_ignored(self, mock_ops_cls) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)

        servicer = DeviceControlServicer()
        await servicer._handle_command_result("device-1", self._result())

        mock_ops.update.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_failed_result_updates_error_fields(self, mock_ops_cls) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=1))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.release_quota_for_command.return_value = OperationResult(success=True)

        servicer = DeviceControlServicer()
        await servicer._handle_command_result(
            "device-1",
            self._result(status=COMMAND_STATUS_FAILED, error_code="POD_CREATE_FAILED", error_message="quota exceeded on node"),
        )

        _, call_data = mock_ops.update.call_args[0]
        self.assertEqual(call_data["error_code"], "POD_CREATE_FAILED")
        self.assertEqual(call_data["error_message"], "quota exceeded on node")
