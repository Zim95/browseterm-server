'''
Migration Part 12: POST /devices/{device_id}/containers/{container_id}/hibernate-request -
Bearer device-token gated, the one new Cloud HTTP surface Device Agent's local API needs
(everything else forwards over the existing control stream instead).
'''
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.container_handlers as container_handlers

USER_A = "user-a"
DEVICE_A = "device-a-id"
CONTAINER_A = "container-a-id"


def _mock_request(path_params: dict, device_id: str = DEVICE_A, user_id: str = USER_A) -> MagicMock:
    request = MagicMock(spec=Request)
    request.path_params = path_params
    request.state.device_id = device_id
    request.state.user_id = user_id
    request.state.scopes = []
    return request


class TestRequestHibernateCommand(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_happy_path_creates_hibernate_command(self, mock_container_ops_cls, mock_command_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={
                "id": CONTAINER_A, "user_id": USER_A, "device_id": DEVICE_A, "status": "Running",
                "name": "t1", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi", "placement_generation": 1,
            },
        )
        mock_command_ops_cls.return_value.insert.return_value = OperationResult(success=True, data={"id": "cmd-1"})
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=True)

        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await container_handlers.request_hibernate_command.__wrapped__(request)

        self.assertEqual(response.status_code, 202)

    async def test_device_id_mismatch_is_not_found(self) -> None:
        request = _mock_request({"device_id": "some-other-device", "container_id": CONTAINER_A})
        response = await container_handlers.request_hibernate_command.__wrapped__(request)
        self.assertEqual(response.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_container_not_owned_by_this_device_is_not_found(self, mock_container_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await container_handlers.request_hibernate_command.__wrapped__(request)
        self.assertEqual(response.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_non_running_container_is_rejected(self, mock_container_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": CONTAINER_A, "user_id": USER_A, "device_id": DEVICE_A, "status": "Hibernated"},
        )
        request = _mock_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        response = await container_handlers.request_hibernate_command.__wrapped__(request)
        self.assertEqual(response.status_code, 409)
