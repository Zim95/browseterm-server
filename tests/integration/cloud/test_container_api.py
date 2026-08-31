'''
Cloud container/workspace metadata API tests. Same "mock the boundary" convention as
test_device_api.py: call the handler directly, patch ContainerOps/ImageOps/SubscriptionTypeOps
at their import site in src.cloud.container_handlers.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.models.containers import ContainerStatus
from browseterm_db.models.devices import DeviceStatus
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


DEVICE_A = "device-a-id"


def _container_row(**overrides) -> dict:
    row = {"id": CONTAINER_A, "user_id": USER_A, "name": "my-workspace", "status": "Running"}
    row.update(overrides)
    return row


def _device_row(**overrides) -> dict:
    row = {
        "id": DEVICE_A, "user_id": USER_A, "status": "Active",
        "allocated_cpu": 4, "used_cpu": 0,
        "allocated_memory_bytes": 8 * 1024 ** 3, "used_memory_bytes": 0,
        "allocated_storage_bytes": 100 * 1024 ** 3, "used_storage_bytes": 0,
    }
    row.update(overrides)
    return row


def _create_body(**overrides) -> dict:
    body = {
        "user_id": USER_A, "name": "my-workspace", "device_id": DEVICE_A,
        "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi",
        "image_id": "img1", "port_mappings": [],
    }
    body.update(overrides)
    return body


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
    '''P12: create_container now also validates the device and requested resources, and reserves
    usage against the device before creating the row (see the plan's own bullet order for this
    task in section 22's P12 entry).'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_create_succeeds_and_reserves_usage(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops.insert.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(_create_body())
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 201)

        reserve_filters, reserve_data = mock_device_ops.update.call_args.args
        self.assertEqual(reserve_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(reserve_data, {
            "used_cpu": 1, "used_memory_bytes": 1024 ** 3, "used_storage_bytes": 2 * 1024 ** 3,
        })

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_duplicate_name_for_same_user_rejected(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops_cls.return_value = mock_ops
        request = _mock_request(_create_body())
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 409)
        mock_ops.insert.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_fields_rejected(self):
        request = _mock_request({"name": "my-workspace"})
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_invalid_quantity_rejected(self):
        request = _mock_request(_create_body(cpu_limit="not-a-quantity"))
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_device_not_found_rejected(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(_create_body())
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 404)
        mock_device_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_inactive_device_rejected(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row(status="Inactive"))
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(_create_body())
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)
        mock_device_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_over_capacity_request_rejected(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(
            success=True, data=_device_row(allocated_cpu=1, used_cpu=1),  # 0 cores available
        )
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(_create_body(cpu_limit="1"))
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)
        mock_device_ops.update.assert_not_called()
        mock_ops.insert.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_omitted_device_id_resolves_active_device(self, mock_container_ops_cls, mock_device_ops_cls):
        '''P13: browseterm-server-local has no device_id of its own to send - Cloud must resolve
        the caller's currently-ACTIVE device automatically when device_id is omitted.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops.insert.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        body = _create_body()
        del body["device_id"]
        request = _mock_request(body)
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 201)

        mock_device_ops.find_one.assert_called_once_with({"user_id": USER_A, "status": DeviceStatus.ACTIVE})
        insert_data = mock_ops.insert.call_args.args[0]
        self.assertEqual(insert_data["device_id"], DEVICE_A)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_omitted_device_id_with_no_active_device_rejected(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_device_ops_cls.return_value = mock_device_ops

        body = _create_body()
        del body["device_id"]
        request = _mock_request(body)
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 400)
        mock_ops.insert.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_insert_failure_releases_reservation(self, mock_container_ops_cls, mock_device_ops_cls):
        '''Fail/release path: reservation happens before the row is created, so a failed insert
        must give the reservation back.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops.insert.return_value = OperationResult(success=False, error="db exploded")
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(_create_body())
        result = asyncio.run(container_handlers.create_container(request))
        self.assertEqual(result.status_code, 500)

        # First call reserves (used_cpu=1), second call releases it back (used_cpu=0).
        self.assertEqual(mock_device_ops.update.call_count, 2)
        release_filters, release_data = mock_device_ops.update.call_args_list[1].args
        self.assertEqual(release_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(release_data, {"used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0})


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

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_delete_releases_device_resources(self, mock_container_ops_cls, mock_device_ops_cls):
        '''P12: plan section 9 - "On Hibernate/Delete: decrement cached used resources."'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
        ))
        mock_ops.delete.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(
            success=True,
            data=_device_row(used_cpu=1, used_memory_bytes=1024 ** 3, used_storage_bytes=2 * 1024 ** 3),
        )
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request({"user_id": USER_A}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.delete_container(request))
        self.assertEqual(result.status_code, 200)

        release_filters, release_data = mock_device_ops.update.call_args.args
        self.assertEqual(release_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(release_data, {"used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_delete_without_device_id_skips_release(self, mock_container_ops_cls, mock_device_ops_cls):
        '''Legacy/pre-P12 rows with no device_id must not error out on delete.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops.delete.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops_cls.return_value = MagicMock()

        request = _mock_request({"user_id": USER_A}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.delete_container(request))
        self.assertEqual(result.status_code, 200)
        mock_device_ops_cls.return_value.find_one.assert_not_called()


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


class TestUpdateContainerStatus(unittest.TestCase):
    '''POST /internal/containers/{container_id}/status (P09) - no user_id, trusted system caller.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(
            body={"status": "Running"}, path_params={"container_id": CONTAINER_A}, headers={}
        )
        result = asyncio.run(container_handlers.update_container_status(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_status_rejected(self):
        request = _mock_request(body={}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container_status(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_invalid_status_value_rejected(self):
        request = _mock_request(body={"status": "not-a-real-status"}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container_status(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unconditional_update_no_expected_status(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops

        request = _mock_request(body={"status": "Running"}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container_status(request))

        self.assertEqual(result.status_code, 200)
        filters, data = mock_ops.update.call_args.args
        self.assertEqual(filters, {"id": CONTAINER_A})  # no user_id, no status filter
        self.assertEqual(data["status"].value, "Running")

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_conditional_update_with_expected_status_is_atomic_cas(self, mock_ops_cls):
        '''Mirrors the old mark_lost_if_running's exact semantics - a single WHERE id=X AND
        status=expected_status UPDATE, not a read-then-write.'''
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops

        request = _mock_request(
            body={"status": "Hibernated", "expected_status": "Running"},
            path_params={"container_id": CONTAINER_A},
        )
        result = asyncio.run(container_handlers.update_container_status(request))

        self.assertEqual(result.status_code, 200)
        filters, data = mock_ops.update.call_args.args
        self.assertEqual(filters["id"], CONTAINER_A)
        self.assertEqual(filters["status"].value, "Running")
        self.assertEqual(data["status"].value, "Hibernated")

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_zero_rows_matched_is_still_a_success(self, mock_ops_cls):
        '''The conditional filter not matching (row already moved on, or doesn't exist) is a
        harmless no-op, not an error - matches the pre-migration direct-DB behavior exactly.'''
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops

        request = _mock_request(
            body={"status": "Hibernated", "expected_status": "Running"},
            path_params={"container_id": "nonexistent-or-already-moved-on"},
        )
        result = asyncio.run(container_handlers.update_container_status(request))
        self.assertEqual(result.status_code, 200)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_db_failure_returns_500(self, mock_ops_cls):
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_ops_cls.return_value = mock_ops

        request = _mock_request(body={"status": "Running"}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container_status(request))
        self.assertEqual(result.status_code, 500)


class TestReconcileDeviceResources(unittest.TestCase):
    '''P14: POST /internal/devices/resources/reconcile.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(body={"running_container_ids": []}, headers={})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_non_list_body_rejected(self):
        request = _mock_request(body={"running_container_ids": "not-a-list"})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_sums_running_containers_per_device_and_overwrites(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_container_row(
                id="c1", device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
            )),
            OperationResult(success=True, data=_container_row(
                id="c2", device_id=DEVICE_A, cpu_limit="500m", memory_limit="512Mi", storage_limit="1Gi",
            )),
        ]
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(body={"running_container_ids": ["c1", "c2"]})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 200)

        # 1 core + ceil(0.5 core) = 2 cores; 1Gi + 512Mi bytes; 2Gi + 1Gi bytes.
        update_filters, update_data = mock_device_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A})
        self.assertEqual(update_data, {
            "used_cpu": 2,
            "used_memory_bytes": 1024 ** 3 + 512 * 1024 ** 2,
            "used_storage_bytes": 2 * 1024 ** 3 + 1024 ** 3,
        })
        import json
        payload = json.loads(result.body)
        self.assertIn(DEVICE_A, payload["reconciled_devices"])

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_container_with_no_device_id_skipped(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(device_id=None))
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(body={"running_container_ids": [CONTAINER_A]})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 200)
        mock_device_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unknown_container_id_skipped(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(body={"running_container_ids": ["does-not-exist"]})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["reconciled_devices"], {})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_empty_running_list_reconciles_nothing(self, mock_container_ops_cls):
        request = _mock_request(body={"running_container_ids": []})
        result = asyncio.run(container_handlers.reconcile_device_resources(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["reconciled_devices"], {})


class TestListIdleContainers(unittest.TestCase):
    '''P18: GET /internal/devices/{device_id}/containers/idle.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(
            path_params={"device_id": "device-a"}, query_params={"idle_threshold_seconds": "1800"}, headers={},
        )
        result = asyncio.run(container_handlers.list_idle_containers(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_threshold_rejected(self):
        request = _mock_request(path_params={"device_id": "device-a"}, query_params={})
        result = asyncio.run(container_handlers.list_idle_containers(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_non_integer_threshold_rejected(self):
        request = _mock_request(
            path_params={"device_id": "device-a"}, query_params={"idle_threshold_seconds": "not-a-number"},
        )
        result = asyncio.run(container_handlers.list_idle_containers(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_scopes_query_to_the_given_device(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_idle_containers.return_value = OperationResult(success=True, data=[_container_row()])
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(
            path_params={"device_id": "device-a"}, query_params={"idle_threshold_seconds": "1800"},
        )
        result = asyncio.run(container_handlers.list_idle_containers(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.find_idle_containers.assert_called_once_with(1800, "device-a")


class TestHibernateContainer(unittest.TestCase):
    '''P18: POST /internal/containers/{container_id}/hibernate.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(path_params={"container_id": CONTAINER_A}, headers={})
        result = asyncio.run(container_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unknown_container_404s(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 404)
        mock_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_sets_hibernated_clears_device_id_and_releases_resources(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
        ))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(
            success=True,
            data=_device_row(used_cpu=1, used_memory_bytes=1024 ** 3, used_storage_bytes=2 * 1024 ** 3),
        )
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _mock_request(path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 200)

        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": CONTAINER_A})
        self.assertEqual(update_data["status"], ContainerStatus.HIBERNATED)
        self.assertIsNone(update_data["device_id"])

        release_filters, release_data = mock_device_ops.update.call_args.args
        self.assertEqual(release_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(release_data, {"used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_update_failure_returns_500(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 500)


if __name__ == "__main__":
    unittest.main()
