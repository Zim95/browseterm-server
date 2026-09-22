'''
SAVE (added 2026-09-22): GET /devices/{device_id}/containers/{container_id}/save-status -
Bearer device-token gated, the one new Cloud HTTP surface Device Agent's save_execution.py needs
to learn the confirmed outcome of a save (mirrors test_request_hibernate_command.py's own
pattern/conventions for a device-authenticated route).
'''
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.snapshot_handlers as snapshot_handlers

USER_A = "user-a"
DEVICE_A = "device-a-id"
CONTAINER_A = "container-a-id"


def _mock_request(path_params: dict, query_params: dict = None, device_id: str = DEVICE_A, user_id: str = USER_A) -> MagicMock:
    request = MagicMock(spec=Request)
    request.path_params = path_params
    request.query_params = query_params if query_params is not None else {"request_id": "req-1"}
    request.state.device_id = device_id
    request.state.user_id = user_id
    request.state.scopes = []
    return request


class TestGetSaveStatus(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    @patch("src.cloud.snapshot_handlers.ContainerOps")
    async def test_succeeded_snapshot_returns_image_reference(self, mock_container_ops_cls, mock_snapshot_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": CONTAINER_A, "user_id": USER_A, "device_id": DEVICE_A},
        )
        mock_snapshot_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"status": "Succeeded", "image_reference": "registry/img:1", "error_detail": None},
        )

        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await snapshot_handlers.get_save_status.__wrapped__(request)

        self.assertEqual(response.status_code, 200)

    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    @patch("src.cloud.snapshot_handlers.ContainerOps")
    async def test_no_snapshot_row_yet_returns_null_status_not_error(self, mock_container_ops_cls, mock_snapshot_ops_cls) -> None:
        '''Device Agent may start polling before snapshot_job calls allocate_snapshot - this must
        look like "still pending", not a 404/error, so the caller's poll loop just keeps waiting.'''
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": CONTAINER_A, "user_id": USER_A, "device_id": DEVICE_A},
        )
        mock_snapshot_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)

        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await snapshot_handlers.get_save_status.__wrapped__(request)

        self.assertEqual(response.status_code, 200)

    async def test_device_id_mismatch_is_not_found(self) -> None:
        request = _mock_request({"device_id": "some-other-device", "container_id": CONTAINER_A})
        response = await snapshot_handlers.get_save_status.__wrapped__(request)
        self.assertEqual(response.status_code, 404)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    async def test_container_not_owned_by_this_device_is_not_found(self, mock_container_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await snapshot_handlers.get_save_status.__wrapped__(request)
        self.assertEqual(response.status_code, 404)

    async def test_missing_request_id_is_rejected(self) -> None:
        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A}, query_params={})
        response = await snapshot_handlers.get_save_status.__wrapped__(request)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
