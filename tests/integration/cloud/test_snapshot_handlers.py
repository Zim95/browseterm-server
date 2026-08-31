'''
Cloud snapshot allocation API tests (P16). Same "mock the boundary" convention as
test_container_api.py: call the handler directly, patch ContainerOps/SnapshotOps at their import
site in src.cloud.snapshot_handlers.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.snapshot_handlers as snapshot_handlers

TOKEN = "test-internal-token"
CONTAINER_A = "container-a-id"
USER_A = "user-a-id"


def _mock_request(body: dict = None, path_params: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {"container_id": CONTAINER_A}
    request.headers = headers if headers is not None else {"X-Internal-Service-Token": TOKEN}
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _container_row(**overrides) -> dict:
    row = {"id": CONTAINER_A, "user_id": USER_A, "next_snapshot_sequence": 1}
    row.update(overrides)
    return row


def _snapshot_row(**overrides) -> dict:
    row = {
        "id": "snapshot-1", "container_id": CONTAINER_A, "version_sequence": 1,
        "version": "0.0.0.0.1", "image_repository": "browseterm/user-a-id_container-a-id",
        "image_reference": None, "registry_digest": None, "request_id": "req-1",
        "status": "Pending", "error_detail": None,
    }
    row.update(overrides)
    return row


class TestAllocateSnapshot(unittest.TestCase):
    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request({"request_id": "req-1"}, headers={})
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_request_id_rejected(self):
        request = _mock_request({})
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.snapshot_handlers.SnapshotOps")
    def test_existing_request_id_returns_existing_row(self, mock_snapshot_ops_cls):
        mock_snapshot_ops = MagicMock()
        mock_snapshot_ops.find_one.return_value = OperationResult(success=True, data=_snapshot_row())
        mock_snapshot_ops_cls.return_value = mock_snapshot_ops

        request = _mock_request({"request_id": "req-1"})
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 200)
        mock_snapshot_ops.find_one.assert_called_once_with({"container_id": CONTAINER_A, "request_id": "req-1"})
        mock_snapshot_ops.insert.assert_not_called()

    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
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
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 404)
        mock_container_ops.update.assert_not_called()

    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
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
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 201)

        # increments next_snapshot_sequence from 5 -> 6, allocates sequence 5 for this attempt.
        update_filters, update_data = mock_container_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": CONTAINER_A})
        self.assertEqual(update_data, {"next_snapshot_sequence": 6})

        insert_data = mock_snapshot_ops.insert.call_args.args[0]
        self.assertEqual(insert_data["version_sequence"], 5)
        self.assertEqual(insert_data["version"], "0.0.0.0.5")
        self.assertEqual(insert_data["image_repository"], f"browseterm/{USER_A}_{CONTAINER_A}")
        self.assertEqual(insert_data["request_id"], "req-1")

    @patch("src.cloud.snapshot_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
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
        result = asyncio.run(snapshot_handlers.allocate_snapshot(request))
        self.assertEqual(result.status_code, 500)
        mock_snapshot_ops.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
