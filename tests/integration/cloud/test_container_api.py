'''
Cloud container/workspace metadata API tests. Same "mock the boundary" convention as
test_device_api.py: call the handler directly, patch ContainerOps/ImageOps/SubscriptionTypeOps
at their import site in src.cloud.container_handlers.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.container_handlers as container_handlers

TOKEN = "test-internal-token"
USER_A = "user-a"
CONTAINER_A = "container-a-id"


def _mock_request(body: dict = None, path_params: dict = None, query_params: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {}
    request.query_params = query_params or {}
    request.headers = headers if headers is not None else {"X-Internal-Service-Token": TOKEN}
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _container_row(**overrides) -> dict:
    row = {"id": CONTAINER_A, "user_id": USER_A, "name": "my-workspace", "status": "Running"}
    row.update(overrides)
    return row


class TestAuthRequired(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected_on_create(self):
        request = _mock_request({"user_id": USER_A, "name": "x"}, headers={})
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected_on_list(self):
        request = _mock_request(query_params={"user_id": USER_A}, headers={})
        result = asyncio.run(container_handlers.list_containers(request))
        self.assertEqual(result.status_code, 401)


class TestCreateContainer(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_create_succeeds(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops.insert.return_value = OperationResult(success=True, data=_container_row())
        mock_ops_cls.return_value = mock_ops
        request = _mock_request({"user_id": USER_A, "name": "my-workspace", "image_id": "img1", "port_mappings": []})
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 201)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_duplicate_name_for_same_user_rejected(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops_cls.return_value = mock_ops
        request = _mock_request({"user_id": USER_A, "name": "my-workspace"})
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 409)
        mock_ops.insert.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_user_id_rejected(self):
        request = _mock_request({"name": "my-workspace"})
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)


class TestGetContainerOwnership(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_owner_can_get(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops_cls.return_value = mock_ops
        request = _mock_request(path_params={"container_id": CONTAINER_A}, query_params={"user_id": USER_A})
        result = asyncio.run(container_handlers.get_container(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.find_one.assert_called_once_with({"id": CONTAINER_A, "user_id": USER_A})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_non_owner_gets_404(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request(path_params={"container_id": CONTAINER_A}, query_params={"user_id": "user-b"})
        result = asyncio.run(container_handlers.get_container(request))
        self.assertEqual(result.status_code, 404)


class TestUpdateContainer(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_protected_fields_dropped(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_container_row()),
            OperationResult(success=True, data=_container_row(status="Hibernated")),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request(
            {"user_id": USER_A, "id": "spoofed-id", "created_at": "2000-01-01", "status": "Hibernated"},
            path_params={"container_id": CONTAINER_A},
        )
        result = asyncio.run(container_handlers.update_container(request))
        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": CONTAINER_A, "user_id": USER_A})
        self.assertEqual(update_data, {"status": "Hibernated"})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_non_owner_cannot_update(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request({"user_id": "user-b", "status": "Running"}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container(request))
        self.assertEqual(result.status_code, 404)
        mock_ops.update.assert_not_called()


class TestDeleteContainer(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_owner_can_delete(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops.delete.return_value = OperationResult(success=True)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request({"user_id": USER_A}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.delete_container(request))
        self.assertEqual(result.status_code, 200)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_non_owner_cannot_delete(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request({"user_id": "user-b"}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.delete_container(request))
        self.assertEqual(result.status_code, 404)
        mock_ops.delete.assert_not_called()


class TestCatalog(unittest.TestCase):
    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ImageOps")
    def test_list_images(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[{"id": "img1"}])
        mock_ops_cls.return_value = mock_ops
        request = _mock_request()
        result = asyncio.run(container_handlers.list_images(request))
        self.assertEqual(result.status_code, 200)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.SubscriptionTypeOps")
    def test_list_subscription_types(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[{"id": "sub1"}])
        mock_ops_cls.return_value = mock_ops
        request = _mock_request()
        result = asyncio.run(container_handlers.list_subscription_types(request))
        self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()
