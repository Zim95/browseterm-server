'''
apply_terminal_command_result's own logic (extracted 2026-09-26 from servicer.py's
_handle_command_result so the new HTTP result-reporting path - src/cloud/
device_command_result_handlers.py - could reuse it verbatim). Doc-required behavior covered here:
"stale device/generation result rejected", "duplicate delivery is expected and safe".
'''
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from browseterm_db.operations import OperationResult

from src.control.command_result_ops import apply_terminal_command_result


def _command_row(**overrides) -> dict:
    row = {
        "id": "cmd-1", "user_id": "user-1", "device_id": "device-1", "container_id": "container-1",
        "operation": "Create", "placement_generation": 1, "expected_container_state": None,
        "status": "Queued", "attempt_count": 0, "request_id": None, "correlation_id": "trace-1",
    }
    row.update(overrides)
    return row


class TestApplyTerminalCommandResult(IsolatedAsyncioTestCase):

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_matching_generation_success_updates_and_releases_quota(self, mock_ops_cls, mock_apply_command_result) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=1))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.release_quota_for_command.return_value = OperationResult(success=True)

        await apply_terminal_command_result("device-1", "cmd-1", "succeeded", None, None, None, 1)

        mock_ops.update.assert_called_once()
        mock_ops.release_quota_for_command.assert_called_once_with("cmd-1")
        mock_apply_command_result.assert_called_once()

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_stale_placement_generation_is_rejected(self, mock_ops_cls, mock_apply_command_result) -> None:
        '''Doc-required: "stale device/generation result rejected."'''
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=2))

        await apply_terminal_command_result("device-1", "cmd-1", "succeeded", None, None, None, 1)

        mock_ops.update.assert_not_called()
        mock_ops.release_quota_for_command.assert_not_called()
        mock_apply_command_result.assert_not_called()

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_already_terminal_command_result_is_a_no_op(self, mock_ops_cls, mock_apply_command_result) -> None:
        '''Doc-required: "duplicate delivery is expected and safe" - a second CommandResult for
        an already-SUCCEEDED command must not double-release quota or re-write the row. Also the
        exact case that makes receiving the same result over BOTH the stream and the new HTTP
        path harmless.'''
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(status="Succeeded", placement_generation=1))

        await apply_terminal_command_result("device-1", "cmd-1", "succeeded", None, None, None, 1)

        mock_ops.update.assert_not_called()
        mock_ops.release_quota_for_command.assert_not_called()
        mock_apply_command_result.assert_not_called()

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_result_for_unknown_command_is_ignored(self, mock_ops_cls, mock_apply_command_result) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)

        await apply_terminal_command_result("device-1", "cmd-1", "succeeded", None, None, None, 1)

        mock_ops.update.assert_not_called()
        mock_apply_command_result.assert_not_called()

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_failed_result_updates_error_fields(self, mock_ops_cls, mock_apply_command_result) -> None:
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_one.return_value = OperationResult(success=True, data=_command_row(placement_generation=1))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.release_quota_for_command.return_value = OperationResult(success=True)

        await apply_terminal_command_result(
            "device-1", "cmd-1", "failed", None, "POD_CREATE_FAILED", "quota exceeded on node", 1,
        )

        _, call_data = mock_ops.update.call_args[0]
        self.assertEqual(call_data["error_code"], "POD_CREATE_FAILED")
        self.assertEqual(call_data["error_message"], "quota exceeded on node")
        mock_apply_command_result.assert_called_once_with(
            _command_row(placement_generation=1), "failed", None, "quota exceeded on node",
        )

    @patch("src.control.command_result_ops.apply_command_result")
    @patch("src.control.command_result_ops.DeviceCommandOps")
    async def test_non_terminal_status_is_ignored(self, mock_ops_cls, mock_apply_command_result) -> None:
        await apply_terminal_command_result("device-1", "cmd-1", "running", None, None, None, 1)

        mock_ops_cls.return_value.find_one.assert_not_called()
        mock_apply_command_result.assert_not_called()
