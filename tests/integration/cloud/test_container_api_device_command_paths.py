'''
Migration Parts 8-11: the feature-flagged device-command paths in container_handlers.py, gated
by DEVICE_COMMAND_CREATE_ENABLED/DELETE_ENABLED/HIBERNATE_ENABLED/RESUME_ENABLED. Same
"mock the boundary" convention as test_container_api.py - patch ContainerOps/DeviceOps/
DeviceCommandOps/ImageOps at their import site in src.cloud.container_handlers, and the feature
flags themselves (default False - these tests turn them on explicitly).
'''
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.container_handlers as container_handlers

TOKEN = "test-internal-token"
USER_A = "user-a"
DEVICE_A = "device-a-id"
CONTAINER_A = "container-a-id"


def _mock_request(body: dict = None, path_params: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {}
    request.headers = {"X-Internal-Service-Token": TOKEN}
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _device_row(**overrides) -> dict:
    row = {
        "id": DEVICE_A, "user_id": USER_A, "status": "Active",
        "allocated_cpu": 4, "used_cpu": 0,
        "allocated_memory_bytes": 8 * 1024 ** 3, "used_memory_bytes": 0,
        "allocated_storage_bytes": 100 * 1024 ** 3, "used_storage_bytes": 0,
    }
    row.update(overrides)
    return row


def _container_row(**overrides) -> dict:
    row = {
        "id": CONTAINER_A, "user_id": USER_A, "name": "my-workspace", "status": "Hibernated",
        "device_id": DEVICE_A, "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi",
        "placement_generation": 1, "saved_image": "registry/img:1", "port_mappings": None, "environment_vars": None,
    }
    row.update(overrides)
    return row


class TestCreateContainerViaDeviceCommand(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_CREATE_ENABLED", True)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.ImageOps")
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_happy_path_returns_202_with_container_and_command(
        self, mock_container_ops_cls, mock_device_ops_cls, mock_image_ops_cls, mock_command_ops_cls,
    ) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)  # no name clash
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_image_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data={"id": "img-1", "image": "browseterm/base:latest"})
        mock_container_ops_cls.return_value.insert.return_value = OperationResult(success=True, data=_container_row(status="Queued"))
        mock_command_ops_cls.return_value.reserve_quota_and_create_command.return_value = OperationResult(
            success=True, data={"id": "cmd-1", "status": "Queued"},
        )
        mock_command_ops_cls.return_value.update.return_value = OperationResult(success=True)

        request = _mock_request({
            "user_id": USER_A, "name": "my-workspace", "device_id": DEVICE_A, "image_id": "img-1",
            "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi",
        })
        response = await container_handlers.create_container(request)

        self.assertEqual(response.status_code, 202)
        mock_command_ops_cls.return_value.reserve_quota_and_create_command.assert_called_once()
        # Regression test for a real production bug: container_config_json used to be patched in
        # via a separate command_ops.update() call AFTER the command row was already inserted -
        # CommandBroadcaster (Postgres LISTEN/NOTIFY) can dispatch the command to Device Agent in
        # that exact gap, delivering an ExecuteCommand with an empty container_config_json, which
        # Device Agent instantly rejects ("container_config_json was missing or not valid JSON").
        # Nothing this depends on (image name, container name, network name) is unknown before
        # the command is created, so it must be included in the same call, not patched in after.
        _, kwargs = mock_command_ops_cls.return_value.reserve_quota_and_create_command.call_args
        self.assertIsNotNone(kwargs.get("container_config_json"))
        mock_command_ops_cls.return_value.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_CREATE_ENABLED", True)
    @patch("src.cloud.container_handlers.ImageOps")
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_missing_image_id_is_rejected(self, mock_container_ops_cls, mock_device_ops_cls, mock_image_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_device_row())

        request = _mock_request({
            "user_id": USER_A, "name": "my-workspace", "device_id": DEVICE_A,
            "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi",
        })
        response = await container_handlers.create_container(request)
        self.assertEqual(response.status_code, 400)


class TestDeleteContainerViaDeviceCommand(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_DELETE_ENABLED", True)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_creates_delete_command_and_marks_deleting(self, mock_container_ops_cls, mock_command_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"))
        mock_command_ops_cls.return_value.insert.return_value = OperationResult(success=True, data={"id": "cmd-1"})
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=True)

        request = _mock_request({"user_id": USER_A}, {"container_id": CONTAINER_A})
        response = await container_handlers.delete_container(request)

        self.assertEqual(response.status_code, 202)
        mock_container_ops_cls.return_value.delete.assert_not_called()  # row must NOT be deleted eagerly
        update_call = mock_container_ops_cls.return_value.update.call_args[0]
        self.assertEqual(update_call[1]["status"].value, "Deleting")


class TestHibernateContainerViaDeviceCommand(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_HIBERNATE_ENABLED", True)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_creates_hibernate_command_and_marks_hibernating(self, mock_container_ops_cls, mock_command_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"))
        mock_command_ops_cls.return_value.insert.return_value = OperationResult(success=True, data={"id": "cmd-1"})
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=True)

        request = _mock_request({}, {"container_id": CONTAINER_A})
        response = await container_handlers.hibernate_container(request)

        self.assertEqual(response.status_code, 202)
        update_call = mock_container_ops_cls.return_value.update.call_args[0]
        self.assertEqual(update_call[1]["status"].value, "Hibernating")


class TestSaveContainerViaDeviceCommand(unittest.IsolatedAsyncioTestCase):
    '''Unlike Create/Delete/Hibernate/Resume, _save_container_via_device_command has no public
    internal-token route of its own - it's called from src.cloud.browser_handlers.save_container
    (session-authenticated) directly, so it's tested as a unit here rather than through a route
    wrapper (browser_handlers.py's own tests cover the auth/CSRF/ownership boundary around it).'''
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    async def test_creates_save_command_without_status_transition(self, mock_command_ops_cls) -> None:
        mock_command_ops_cls.return_value.insert.return_value = OperationResult(success=True, data={"id": "cmd-1"})

        response = await container_handlers._save_container_via_device_command(_container_row(status="Running"))

        self.assertEqual(response.status_code, 202)
        insert_call = mock_command_ops_cls.return_value.insert.call_args[0][0]
        self.assertEqual(insert_call["operation"].value, "Save")

    @patch("src.cloud.container_handlers.DeviceCommandOps")
    async def test_command_creation_failure_returns_500(self, mock_command_ops_cls) -> None:
        mock_command_ops_cls.return_value.insert.return_value = OperationResult(success=False, error="only one active command per container")

        response = await container_handlers._save_container_via_device_command(_container_row(status="Running"))

        self.assertEqual(response.status_code, 500)


class TestResumeContainerViaDeviceCommand(unittest.IsolatedAsyncioTestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_RESUME_ENABLED", True)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_happy_path_reserves_quota_and_returns_202(self, mock_container_ops_cls, mock_device_ops_cls, mock_command_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_command_ops_cls.return_value.reserve_quota_and_create_command.return_value = OperationResult(
            success=True, data={"id": "cmd-1", "placement_generation": 2},
        )
        mock_command_ops_cls.return_value.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=True)

        request = _mock_request({"user_id": USER_A, "device_id": DEVICE_A}, {"container_id": CONTAINER_A})
        response = await container_handlers.resume_container(request)

        self.assertEqual(response.status_code, 202)
        mock_command_ops_cls.return_value.reserve_quota_and_create_command.assert_called_once()
        # Regression test - see the matching CREATE test's comment for the production bug this
        # guards against (container_config_json must be in the same insert, not patched in later).
        _, kwargs = mock_command_ops_cls.return_value.reserve_quota_and_create_command.call_args
        self.assertIsNotNone(kwargs.get("container_config_json"))
        mock_command_ops_cls.return_value.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DEVICE_COMMAND_RESUME_ENABLED", True)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    async def test_missing_saved_image_is_rejected(self, mock_container_ops_cls, mock_device_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(saved_image=None))
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_device_row())

        request = _mock_request({"user_id": USER_A, "device_id": DEVICE_A}, {"container_id": CONTAINER_A})
        response = await container_handlers.resume_container(request)
        self.assertEqual(response.status_code, 409)
