'''
Cloud snapshot allocation/report API tests (P16/P17). Same "mock the boundary" convention as
test_container_api.py: call the handler via its .__wrapped__ (bypassing @authenticate_device's own
Bearer-token parsing) and set request.state directly - matches test_save_status.py's convention
for this file's third @authenticate_device route, get_save_status.

Finishes Part 12: both routes below are now device-Bearer-token gated (POST
/devices/{device_id}/containers/{container_id}/snapshots/...), not internal-token gated - the old
/internal/containers/{container_id}/snapshots/... routes are gone, since snapshot_job was their
only caller.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.snapshot_handlers as snapshot_handlers

CONTAINER_A = "container-a-id"
USER_A = "user-a-id"
DEVICE_A = "device-a-id"


def _mock_request(body: dict = None, path_params: dict = None, device_id: str = DEVICE_A, user_id: str = USER_A) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {"device_id": DEVICE_A, "container_id": CONTAINER_A}
    request.state.device_id = device_id
    request.state.user_id = user_id
    request.state.scopes = []
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _container_row(**overrides) -> dict:
    row = {"id": CONTAINER_A, "user_id": USER_A, "device_id": DEVICE_A, "next_snapshot_sequence": 1}
    row.update(overrides)
    return row


def _snapshot_row(**overrides) -> dict:
    row = {
        "id": "snapshot-1", "container_id": CONTAINER_A, "version_sequence": 1,
        "version": "0.0.0.0.1", "image_repository": "zim95/browseterm",
        "image_tag": f"u_{USER_A}_c_{CONTAINER_A}_v_0.0.0.0.1",
        "image_reference": None, "registry_digest": None, "request_id": "req-1",
        "status": "Pending", "error_detail": None,
    }
    row.update(overrides)
    return row


class TestAllocateSnapshot(unittest.TestCase):
    def test_device_id_mismatch_is_not_found(self):
        request = _mock_request({"request_id": "req-1"}, path_params={"device_id": "some-other-device", "container_id": CONTAINER_A})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    def test_missing_request_id_rejected(self):
        request = _mock_request({})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_existing_request_id_returns_existing_row(self, mock_snapshot_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=_snapshot_row())
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops

        request = _mock_request({"request_id": "req-1"})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_snapshot_ops.find_one.assert_called_once_with({"container_id": CONTAINER_A, "request_id": "req-1"})
        mock_snapshot_ops.insert.assert_not_called()

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_container_not_found_rejected(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_container_ops

        request = _mock_request({"request_id": "req-1"})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 404)
        mock_container_ops.update.assert_not_called()

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_allocates_next_sequence_and_creates_row(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_snapshot_ops.insert.return_value = OperationResult(success=True, data=_snapshot_row())
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops

        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row(next_snapshot_sequence=5))
        mock_container_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_container_ops

        request = _mock_request({"request_id": "req-1"})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 201)

        mock_container_ops.find_one.assert_called_once_with({"id": CONTAINER_A, "device_id": DEVICE_A})

        # increments next_snapshot_sequence from 5 -> 6, allocates sequence 5 for this attempt.
        update_filters, update_data = mock_container_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": CONTAINER_A})
        self.assertEqual(update_data, {"next_snapshot_sequence": 6})

        insert_data = mock_snapshot_ops.insert.call_args.args[0]
        self.assertEqual(insert_data["version_sequence"], 5)
        self.assertEqual(insert_data["version"], "0.0.0.0.5")
        # Part 19: every snapshot goes to the same fixed repository - image_repository is no
        # longer derived from user/container, only image_tag carries that identity.
        self.assertEqual(insert_data["image_repository"], "zim95/browseterm")
        self.assertEqual(insert_data["image_tag"], f"u_{USER_A}_c_{CONTAINER_A}_v_0.0.0.0.5")
        self.assertEqual(insert_data["request_id"], "req-1")

    @patch("src.cloud.snapshot_handlers.SNAPSHOT_REGISTRY_REPO_PREFIX", "myaccount/myrepo")
    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_repository_is_configurable(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_snapshot_ops.insert.return_value = OperationResult(success=True, data=_snapshot_row())
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_container_ops

        request = _mock_request({"request_id": "req-1"})
        asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))

        insert_data = mock_snapshot_ops.insert.call_args.args[0]
        self.assertEqual(insert_data["image_repository"], "myaccount/myrepo")

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_increment_failure_returns_500_without_creating_row(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops

        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_container_ops_cls.return_value = mock_container_ops

        request = _mock_request({"request_id": "req-1"})
        result = asyncio.run(snapshot_handlers.allocate_snapshot.__wrapped__(request))
        self.assertEqual(result.status_code, 500)
        mock_snapshot_ops.insert.assert_not_called()


class TestReportSnapshotResult(unittest.TestCase):
    def _request(self, body: dict, path_params: dict = None, device_id: str = DEVICE_A) -> MagicMock:
        return _mock_request(
            body,
            path_params=path_params or {"device_id": DEVICE_A, "container_id": CONTAINER_A, "snapshot_id": "snapshot-1"},
            device_id=device_id,
        )

    def test_device_id_mismatch_is_not_found(self):
        request = self._request(
            {"status": "Running"},
            path_params={"device_id": "some-other-device", "container_id": CONTAINER_A, "snapshot_id": "snapshot-1"},
        )
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    def test_container_not_owned_by_device_is_not_found(self, mock_container_ops_cls):
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        request = self._request({"status": "Running"})
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    def test_invalid_status_rejected(self, mock_container_ops_cls):
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row())
        request = self._request({"status": "Pending"})  # not a valid report-time status
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_running_updates_both_rows_without_touching_saved_image(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.update.return_value = OperationResult(success=True)
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_container_ops

        request = self._request({"status": "Running"})
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 200)

        snapshot_filters, snapshot_data = mock_snapshot_ops.update.call_args.args
        self.assertEqual(snapshot_filters, {"id": "snapshot-1", "container_id": CONTAINER_A})
        self.assertEqual(snapshot_data["status"], "Running")
        self.assertNotIn("completed_at", snapshot_data)

        container_filters, container_data = mock_container_ops.update.call_args.args
        self.assertEqual(container_filters, {"id": CONTAINER_A})
        self.assertEqual(container_data, {"save_status": "Running", "save_error": None})
        self.assertNotIn("saved_image", container_data)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_succeeded_sets_saved_image_and_last_saved_at(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.update.return_value = OperationResult(success=True)
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_container_ops

        request = self._request({
            "status": "Succeeded",
            "image_reference": "browseterm/user-a-id_container-a-id:0.0.0.0.1",
            "registry_digest": "sha256:abc123",
        })
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 200)

        snapshot_data = mock_snapshot_ops.update.call_args.args[1]
        self.assertEqual(snapshot_data["image_reference"], "browseterm/user-a-id_container-a-id:0.0.0.0.1")
        self.assertEqual(snapshot_data["registry_digest"], "sha256:abc123")
        self.assertIn("completed_at", snapshot_data)

        container_data = mock_container_ops.update.call_args.args[1]
        self.assertEqual(container_data["saved_image"], "browseterm/user-a-id_container-a-id:0.0.0.0.1")
        self.assertIn("last_saved_at", container_data)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_failed_never_touches_saved_image(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        '''Plan section 13: "On failure, saved_image must remain unchanged."'''
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.update.return_value = OperationResult(success=True)
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_container_ops

        request = self._request({"status": "Failed", "error_detail": "docker push failed"})
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 200)

        container_data = mock_container_ops.update.call_args.args[1]
        self.assertEqual(container_data, {"save_status": "Failed", "save_error": "docker push failed"})
        self.assertNotIn("saved_image", container_data)
        self.assertNotIn("last_saved_at", container_data)

    @patch("src.cloud.snapshot_handlers.ContainerOps")
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_snapshot_update_failure_returns_500_before_touching_container(self, mock_snapshot_ops_cls, mock_container_ops_cls):
        mock_container_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops

        request = self._request({"status": "Running"})
        result = asyncio.run(snapshot_handlers.report_snapshot_result.__wrapped__(request))
        self.assertEqual(result.status_code, 500)


if __name__ == "__main__":
    unittest.main()
