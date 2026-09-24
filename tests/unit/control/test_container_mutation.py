import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from browseterm_db.models.containers import ContainerStatus
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

    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_create_success_immediately_applies_used_resources(
        self, mock_command_ops_cls, mock_container_ops_cls, mock_device_ops_cls,
    ) -> None:
        '''
        Regression test for a real production bug: devices.used_* only ever changed via
        status_monitor's resource_reconciler.py, a drift-repair poller with a 300s default
        interval - a container's pod could be genuinely Running and consuming real capacity for
        up to 5 minutes while the device's own used_cpu/used_memory_bytes/used_storage_bytes
        stayed at their pre-create values, so a second create request saw stale "available"
        capacity. A successful CREATE/RESUME result must apply the container's own resource
        limits to used_* immediately, not wait for the next reconcile pass.
        '''
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "c1", "user_id": "u1", "device_id": "d1", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi"},
        )
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0},
        )
        result_json = json.dumps({"kubernetes_id": "pod-1", "ip_address": "10.0.0.1", "associated_resources": {}})

        await apply_command_result(_command(container_id="c1", user_id="u1"), "succeeded", result_json, None)

        mock_device_ops_cls.return_value.update.assert_called_once_with(
            {"id": "d1", "user_id": "u1"},
            {"used_cpu": 1, "used_memory_bytes": 1024 ** 3, "used_storage_bytes": 2 * 1024 ** 3},
        )

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
    async def test_failed_delete_reverts_the_immediate_soft_delete(self, mock_container_ops_cls) -> None:
        '''
        Regression test: delete_container now soft-deletes (deleted_at stamped) the instant it's
        requested, before Device Agent has confirmed anything, so the container disappears from
        the user's list and frees its name right away. A confirmed FAILURE here must undo that -
        otherwise a container whose teardown genuinely failed would vanish from the user's view
        forever with a real, orphaned pod still running and no way to see or retry it.
        '''
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=True)
        await apply_command_result(_command(operation="Delete", container_id="c1", user_id="u1"), "failed", None, "connection refused")
        mock_container_ops_cls.return_value.update.assert_called_once_with(
            {"id": "c1", "user_id": "u1"}, {"deleted_at": None},
        )

    @patch("src.control.container_mutation.ContainerOps")
    async def test_failed_delete_revert_logs_but_does_not_raise_on_name_collision(self, mock_container_ops_cls) -> None:
        '''If a new container has since claimed this name (possible now that the name frees up
        immediately), the partial unique index rejects the revert - ContainerOps.update already
        catches that as a clean OperationResult(success=False), so this must not raise, and must
        leave the container soft-deleted rather than attempt anything more elaborate.'''
        mock_container_ops_cls.return_value.update.return_value = OperationResult(success=False, error="duplicate key")
        await apply_command_result(_command(operation="Delete"), "failed", None, "connection refused")  # must not raise
        mock_container_ops_cls.return_value.delete.assert_not_called()

    @patch("src.control.container_mutation.ContainerOps")
    async def test_delete_for_already_gone_container_is_a_no_op(self, mock_container_ops_cls) -> None:
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        await apply_command_result(_command(operation="Delete"), "succeeded", None, None)
        mock_container_ops_cls.return_value.delete.assert_not_called()

    @patch("src.control.container_mutation.DeviceCommandOps")
    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    async def test_delete_releases_unreleased_command_quota_before_row_is_gone(
        self, mock_container_ops_cls, mock_device_ops_cls, mock_command_ops_cls,
    ) -> None:
        '''
        Regression test: an earlier CREATE/RESUME command may still hold an unreleased quota
        reservation (its terminal CommandResult never reached Cloud, or its status was corrected
        by hand without going through release_quota_for_command). Deleting the container here
        must release that reservation first - device_commands.container_id's ON DELETE CASCADE
        would otherwise remove the only row it could ever be released against, permanently
        stranding devices.reserved_* and blocking every future create/resume with "Insufficient
        device quota" even though nothing is actually in use.
        '''
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "c1", "user_id": "u1", "device_id": None, "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi"},
        )
        mock_container_ops_cls.return_value.delete.return_value = OperationResult(success=True)
        mock_command_ops_cls.return_value.find.return_value = OperationResult(success=True, data=[
            {"id": "cmd-stuck", "quota_reserved_cpu": 2, "quota_released_at": None},
            {"id": "cmd-already-released", "quota_reserved_cpu": 1, "quota_released_at": "2026-09-01T00:00:00Z"},
        ])

        call_order = []
        mock_command_ops_cls.return_value.release_quota_for_command.side_effect = lambda *a, **k: call_order.append("release") or OperationResult(success=True)
        mock_container_ops_cls.return_value.delete.side_effect = lambda *a, **k: call_order.append("delete") or OperationResult(success=True)

        await apply_command_result(_command(operation="Delete", container_id="c1"), "succeeded", None, None)

        mock_command_ops_cls.return_value.release_quota_for_command.assert_called_once_with("cmd-stuck")
        self.assertEqual(call_order, ["release", "delete"])


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
    async def test_failed_hibernate_reverts_the_optimistic_hibernating_status(self, mock_command_ops_cls) -> None:
        '''
        Regression test for a real production bug: _hibernate_container_via_device_command
        optimistically sets status=HIBERNATING the instant the command is created, but nothing
        ever reverted that on a confirmed failure - the container got stuck in HIBERNATING
        forever (an endless loading spinner, no controls, no way to retry) even though the real
        pod was never touched and was fine the whole time. Caught live: a genuine snapshot
        failure (container-maker's REPO_NAME/REPO_PASSWORD not configured) left a container
        stranded exactly this way the same day HIBERNATE_ENABLED was first flipped on. Must
        revert to RUNNING, mirroring how _apply_delete already undoes its own optimistic
        soft-delete on a confirmed failure.
        '''
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        await apply_command_result(_command(operation="Hibernate"), "failed", json.dumps({"saved_image": "registry/img:2"}), "delete failed")
        mock_command_ops_cls.return_value.conditional_container_update.assert_called_once_with(
            "c1", "d1", 2, {"status": ContainerStatus.RUNNING},
        )

    @patch("src.control.container_mutation.DeviceOps")
    @patch("src.control.container_mutation.ContainerOps")
    @patch("src.control.container_mutation.DeviceCommandOps")
    async def test_successful_hibernate_also_releases_unreleased_command_quota(
        self, mock_command_ops_cls, mock_container_ops_cls, mock_device_ops_cls,
    ) -> None:
        '''
        Same class of bug as _apply_delete's own regression test: an earlier CREATE/RESUME
        command for this container may hold a reservation that never got released (a lost
        CommandResult, or a status corrected by hand outside release_quota_for_command).
        Hibernate doesn't remove the container row, so there's no CASCADE data-loss risk the way
        delete has - but left unswept, it would sit stranded on the device for as long as the
        container stays hibernated. _apply_hibernate must sweep it too, not just used_*.
        '''
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "c1", "user_id": "u1", "device_id": "d1", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi"},
        )
        mock_command_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "used_cpu": 1, "used_memory_bytes": 1_000_000_000, "used_storage_bytes": 2_000_000_000},
        )
        mock_device_ops_cls.return_value.update.return_value = OperationResult(success=True)
        mock_command_ops_cls.return_value.find.return_value = OperationResult(success=True, data=[
            {"id": "cmd-stuck", "quota_reserved_cpu": 2, "quota_released_at": None},
        ])
        mock_command_ops_cls.return_value.release_quota_for_command.return_value = OperationResult(success=True)

        await apply_command_result(_command(operation="Hibernate", container_id="c1"), "succeeded", json.dumps({"saved_image": "registry/img:2"}), None)

        mock_command_ops_cls.return_value.release_quota_for_command.assert_called_once_with("cmd-stuck")


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
