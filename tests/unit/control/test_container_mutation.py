import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from browseterm_db.operations import OperationResult

from src.control.container_mutation import apply_command_result


def _command(**overrides) -> dict:
    row = {
        "id": "cmd-1", "user_id": "u1", "device_id": "d1", "container_id": "c1",
        "operation": "Create", "placement_generation": 2,
    }
    row.update(overrides)
    return row


class TestApplyCreateOrResume(IsolatedAsyncioTestCase):
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_create_success_sets_running_and_kubernetes_id(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        result_json = json.dumps({"kubernetes_id": "pod-1", "ip_address": "10.0.0.1", "associated_resources": {"network_name": "u1-namespace"}})

        await apply_command_result(_command(), "succeeded", result_json, None)

        call_args = mock_ops_cls.return_value.conditional_container_update.call_args
        container_id, device_id, generation, update_data = call_args[0]
        self.assertEqual(container_id, "c1")
        self.assertEqual(device_id, "d1")
        self.assertEqual(generation, 2)
        self.assertEqual(update_data["kubernetes_id"], "pod-1")

    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_create_failure_sets_failed_status(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        await apply_command_result(_command(operation="Create"), "failed", None, "node full")
        _, _, _, update_data = mock_ops_cls.return_value.conditional_container_update.call_args[0]
        self.assertEqual(update_data["status"].value, "Failed")

    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_resume_failure_returns_to_hibernated(self, mock_ops_cls) -> None:
        '''Doc-required: "release reservation and return to HIBERNATED when safe" (Part 11).'''
        mock_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        await apply_command_result(_command(operation="Resume"), "failed", None, "image pull error")
        _, _, _, update_data = mock_ops_cls.return_value.conditional_container_update.call_args[0]
        self.assertEqual(update_data["status"].value, "Hibernated")

    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_no_container_id_is_a_no_op(self, mock_ops_cls) -> None:
        await apply_command_result(_command(container_id=None), "succeeded", "{}", None)
        mock_ops_cls.return_value.conditional_container_update.assert_not_called()


class TestApplyDelete(IsolatedAsyncioTestCase):
    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    async def test_successful_delete_removes_row_and_releases_resources(self, mock_container_ops_cls, mock_device_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "c1", "user_id": "u1", "device_id": "d1", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi"},
        )
        mock_container_ops_cls.return_value.delete.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "used_cpu": 2, "used_memory_bytes": 2_000_000_000, "used_storage_bytes": 4_000_000_000},
        )
        mock_device_ops_cls.return_value.update.return_value = OperationResult(success=True)

        await apply_command_result(_command(operation="Delete"), "succeeded", None, None)

        mock_container_ops_cls.return_value.delete.assert_called_once_with({"id": "c1", "user_id": "u1"})
        mock_device_ops_cls.return_value.update.assert_called_once()

    @patch("src.control.container_mutation.ContainerOps")
    async def test_failed_delete_does_not_remove_row(self, mock_container_ops_cls) -> None:
        await apply_command_result(_command(operation="Delete"), "failed", None, "connection refused")
        mock_container_ops_cls.return_value.delete.assert_not_called()

    @patch("src.control.container_mutation.ContainerOps")
    async def test_delete_for_already_gone_container_is_a_no_op(self, mock_container_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        await apply_command_result(_command(operation="Delete"), "succeeded", None, None)
        mock_container_ops_cls.return_value.delete.assert_not_called()


class TestApplyHibernate(IsolatedAsyncioTestCase):
    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_successful_hibernate_sets_hibernated_and_saved_image(self, mock_command_ops_cls, mock_container_ops_cls, mock_device_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "c1", "user_id": "u1", "device_id": "d1", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi"},
        )
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "used_cpu": 2, "used_memory_bytes": 2_000_000_000, "used_storage_bytes": 4_000_000_000},
        )
        mock_device_ops_cls.return_value.update.return_value = OperationResult(success=True)

        await apply_command_result(_command(operation="Hibernate"), "succeeded", json.dumps({"saved_image": "registry/img:2"}), None)

        _, _, _, update_data = mock_command_ops_cls.return_value.conditional_container_update.call_args[0]
        self.assertEqual(update_data["status"].value, "Hibernated")
        self.assertEqual(update_data["saved_image"], "registry/img:2")
        self.assertIsNone(update_data["device_id"])
        mock_device_ops_cls.return_value.update.assert_called_once()

    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_failed_hibernate_does_not_mutate_container(self, mock_command_ops_cls) -> None:
        '''"Pod delete failure does not release quota prematurely" - and the container stays
        exactly as it was (still RUNNING, pod still there) rather than being marked HIBERNATED.'''
        await apply_command_result(_command(operation="Hibernate"), "failed", json.dumps({"saved_image": "registry/img:2"}), "delete failed")
        mock_command_ops_cls.return_value.conditional_container_update.assert_not_called()


class TestApplySave(IsolatedAsyncioTestCase):
    '''Unlike Hibernate, a successful Save only ever touches saved_image - never status/device_id
    (the container stays RUNNING throughout), and never releases any device resources (no
    quota was ever reserved for a Save in the first place).'''
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_successful_save_updates_saved_image_only(self, mock_command_ops_cls) -> None:
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})

        await apply_command_result(_command(operation="Save"), "succeeded", json.dumps({"saved_image": "registry/img:3"}), None)

        _, _, _, update_data = mock_command_ops_cls.return_value.conditional_container_update.call_args[0]
        self.assertEqual(update_data, {"saved_image": "registry/img:3"})

    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_failed_save_does_not_mutate_container(self, mock_command_ops_cls) -> None:
        '''report_snapshot_result already left save_status/saved_image exactly as they should be
        on failure - nothing further to apply here.'''
        await apply_command_result(_command(operation="Save"), "failed", None, "snapshot failed")
        mock_command_ops_cls.return_value.conditional_container_update.assert_not_called()

    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_successful_save_never_releases_device_resources(
        self, mock_command_ops_cls, mock_container_ops_cls, mock_device_ops_cls,
    ) -> None:
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})

        await apply_command_result(_command(operation="Save"), "succeeded", json.dumps({"saved_image": "registry/img:3"}), None)

        mock_device_ops_cls.return_value.update.assert_not_called()
