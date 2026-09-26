'''
POST /devices/{device_id}/commands/{command_id}/result (added 2026-09-26) - Bearer device-token
gated, mirrors test_save_status.py's own pattern/conventions for a device-authenticated route. See
src/control/command_result_ops.py's module docstring for why this endpoint exists (Device Agent
reporting a command's outcome over plain HTTP instead of solely the Device Control stream, which
drops every ~30-90s in this environment).
'''
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request

import src.cloud.device_command_result_handlers as handlers

DEVICE_A = "device-a-id"
COMMAND_A = "command-a-id"


def _mock_request(path_params: dict, body: dict, device_id: str = DEVICE_A) -> MagicMock:
    request = MagicMock(spec=Request)
    request.path_params = path_params
    request.json = AsyncMock(return_value=body)
    request.state.device_id = device_id
    request.state.user_id = "user-a"
    request.state.scopes = []
    return request


class TestReportCommandResult(unittest.IsolatedAsyncioTestCase):

    @patch("src.cloud.device_command_result_handlers.apply_terminal_command_result", new_callable=AsyncMock)
    async def test_succeeded_result_delegates_with_translated_json_result(self, mock_apply) -> None:
        request = _mock_request(
            {"device_id": DEVICE_A, "command_id": COMMAND_A},
            {"status": "succeeded", "result": {"saved_image": "repo:tag"}, "placement_generation": 3},
        )

        response = await handlers.report_command_result.__wrapped__(request)

        self.assertEqual(response.status_code, 200)
        mock_apply.assert_called_once_with(
            DEVICE_A, COMMAND_A, "succeeded", json.dumps({"saved_image": "repo:tag"}), None, None, 3,
        )

    @patch("src.cloud.device_command_result_handlers.apply_terminal_command_result", new_callable=AsyncMock)
    async def test_failed_result_forwards_error_fields(self, mock_apply) -> None:
        request = _mock_request(
            {"device_id": DEVICE_A, "command_id": COMMAND_A},
            {
                "status": "failed", "result": None, "placement_generation": 1,
                "error_code": "POD_DELETE_FAILED", "error_message": "timeout",
            },
        )

        response = await handlers.report_command_result.__wrapped__(request)

        self.assertEqual(response.status_code, 200)
        mock_apply.assert_called_once_with(
            DEVICE_A, COMMAND_A, "failed", None, "POD_DELETE_FAILED", "timeout", 1,
        )

    async def test_device_id_mismatch_is_not_found(self) -> None:
        request = _mock_request(
            {"device_id": "some-other-device", "command_id": COMMAND_A},
            {"status": "succeeded", "placement_generation": 1},
        )
        response = await handlers.report_command_result.__wrapped__(request)
        self.assertEqual(response.status_code, 404)

    async def test_invalid_status_is_rejected(self) -> None:
        request = _mock_request(
            {"device_id": DEVICE_A, "command_id": COMMAND_A},
            {"status": "running", "placement_generation": 1},
        )
        response = await handlers.report_command_result.__wrapped__(request)
        self.assertEqual(response.status_code, 400)

    async def test_missing_placement_generation_is_rejected(self) -> None:
        request = _mock_request(
            {"device_id": DEVICE_A, "command_id": COMMAND_A},
            {"status": "succeeded"},
        )
        response = await handlers.report_command_result.__wrapped__(request)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
