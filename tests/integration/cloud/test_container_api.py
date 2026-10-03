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
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_name_uniqueness_check_excludes_soft_deleted_containers(self, mock_ops_cls):
        '''
        The uniqueness check must ask ContainerOps to exclude soft-deleted rows, not just check
        for any row with the name. DELETE itself no longer soft-deletes at request time (a
        container mid-delete now stays taken/visible - status DELETING - until Device Agent
        confirms and the row is hard-deleted, per the owner's own explicit ask), so this mostly
        guards a legacy/edge path today rather than the everyday DELETE flow, but the exclusion
        must still hold for whatever soft-deleted rows do exist.
        '''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_ops_cls.return_value = mock_ops
        request = _mock_request(_create_body())
        asyncio.run(container_handlers.create_container(request))
        _, kwargs = mock_ops.find_one.call_args
        self.assertTrue(kwargs.get("exclude_deleted"))

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


class TestResumeContainer(unittest.TestCase):
    '''P19: cross-device resume.'''

    def _request(self, body: dict) -> MagicMock:
        return _mock_request(body, path_params={"container_id": CONTAINER_A})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request({"user_id": USER_A}, path_params={"container_id": CONTAINER_A}, headers={})
        result = asyncio.run(container_handlers.resume_container(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unknown_container_404s(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        result = asyncio.run(container_handlers.resume_container(self._request({"user_id": USER_A})))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_non_hibernated_container_rejected(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"))
        mock_container_ops_cls.return_value = mock_ops

        result = asyncio.run(container_handlers.resume_container(self._request({"user_id": USER_A})))
        self.assertEqual(result.status_code, 409)
        mock_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_successful_resume_reserves_and_transitions(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_container_row(
                status="Hibernated", cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi", device_id=None,
            )),
            OperationResult(success=True, data=_container_row(status="Resuming", device_id=DEVICE_A)),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        result = asyncio.run(container_handlers.resume_container(
            self._request({"user_id": USER_A, "device_id": DEVICE_A})
        ))
        self.assertEqual(result.status_code, 200)

        reserve_filters, reserve_data = mock_device_ops.update.call_args_list[0].args
        self.assertEqual(reserve_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(reserve_data, {"used_cpu": 1, "used_memory_bytes": 1024 ** 3, "used_storage_bytes": 2 * 1024 ** 3})

        cas_filters, cas_data = mock_ops.update.call_args.args
        self.assertEqual(cas_filters, {"id": CONTAINER_A, "user_id": USER_A, "status": ContainerStatus.HIBERNATED})
        self.assertEqual(cas_data, {"device_id": DEVICE_A, "status": ContainerStatus.RESUMING})
        # Only reserved once - no release call, since the CAS actually won.
        self.assertEqual(mock_device_ops.update.call_count, 1)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_lost_cas_race_releases_reservation(self, mock_container_ops_cls, mock_device_ops_cls):
        '''Another request already won the resume race between this handler's own read and
        write - the reservation this call made must be given back.'''
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_container_row(
                status="Hibernated", cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi", device_id=None,
            )),
            # Re-fetch shows someone else already resumed it onto a DIFFERENT device.
            OperationResult(success=True, data=_container_row(status="Resuming", device_id="some-other-device")),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        result = asyncio.run(container_handlers.resume_container(
            self._request({"user_id": USER_A, "device_id": DEVICE_A})
        ))
        self.assertEqual(result.status_code, 409)

        # Reserved, then released back - net zero.
        self.assertEqual(mock_device_ops.update.call_count, 2)
        release_filters, release_data = mock_device_ops.update.call_args_list[1].args
        self.assertEqual(release_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(release_data, {"used_cpu": 0, "used_memory_bytes": 0, "used_storage_bytes": 0})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_over_capacity_device_rejected_before_any_reservation(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            status="Hibernated", cpu_limit="5", memory_limit="1Gi", storage_limit="2Gi",
        ))
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(
            success=True, data=_device_row(allocated_cpu=1, used_cpu=1),
        )
        mock_device_ops_cls.return_value = mock_device_ops

        result = asyncio.run(container_handlers.resume_container(
            self._request({"user_id": USER_A, "device_id": DEVICE_A})
        ))
        self.assertEqual(result.status_code, 400)
        mock_device_ops.update.assert_not_called()
        mock_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_omitted_device_id_resolves_active_device(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_container_row(
                status="Hibernated", cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi", device_id=None,
            )),
            OperationResult(success=True, data=_container_row(status="Resuming", device_id=DEVICE_A)),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        result = asyncio.run(container_handlers.resume_container(self._request({"user_id": USER_A})))
        self.assertEqual(result.status_code, 200)
        mock_device_ops.find_one.assert_called_once_with({"user_id": USER_A, "status": DeviceStatus.ACTIVE})


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

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_delete_releases_unreleased_command_quota_before_row_is_gone(
        self, mock_container_ops_cls, mock_device_ops_cls, mock_command_ops_cls,
    ):
        '''
        Regression test: a CREATE/RESUME command reserves quota into devices.reserved_* and only
        releases it once a terminal CommandResult arrives over gRPC. If that never happened (lost
        connection, or a command row corrected by hand) and the container is then deleted here,
        device_commands.container_id's ON DELETE CASCADE would remove the only row the
        reservation could ever be released against - stranding devices.reserved_* forever and
        making every future create/resume fail with "Insufficient device quota" even though
        nothing is actually in use. delete_container must release any such stray reservation
        before the container row (and its cascade-linked commands) disappear.
        '''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(device_id=None))
        mock_ops.delete.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_command_ops = MagicMock()
        mock_command_ops.find.return_value = OperationResult(success=True, data=[
            {"id": "cmd-stuck", "quota_reserved_cpu": 2, "quota_released_at": None},
            {"id": "cmd-already-released", "quota_reserved_cpu": 1, "quota_released_at": "2026-09-01T00:00:00Z"},
            {"id": "cmd-delete", "quota_reserved_cpu": None, "quota_released_at": None},
        ])
        mock_command_ops.release_quota_for_command.return_value = OperationResult(success=True)
        mock_command_ops_cls.return_value = mock_command_ops

        # Track call order across both mocks to prove the reservation is released before the
        # row (and its cascade-linked command) is deleted, not after.
        call_order = []
        mock_command_ops.release_quota_for_command.side_effect = lambda *a, **k: call_order.append("release") or OperationResult(success=True)
        mock_ops.delete.side_effect = lambda *a, **k: call_order.append("delete") or OperationResult(success=True)

        request = _mock_request({"user_id": USER_A}, path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.delete_container(request))

        self.assertEqual(result.status_code, 200)
        mock_command_ops.release_quota_for_command.assert_called_once_with("cmd-stuck")
        self.assertEqual(call_order, ["release", "delete"])


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


def _device_auth_request(path_params: dict, body: dict = None, device_id: str = DEVICE_A, user_id: str = USER_A) -> MagicMock:
    '''Shared convention for the @authenticate_device-gated routes below (matches
    test_save_status.py) - call the handler via its .__wrapped__ to bypass the decorator's own
    Bearer-token parsing entirely and set request.state directly, same as a real validated token
    would.'''
    request = _mock_request(body=body, path_params=path_params)
    request.state.device_id = device_id
    request.state.user_id = user_id
    request.state.scopes = []
    return request


class TestReconcileDeviceResources(unittest.TestCase):
    '''Finishes Part 12: POST /devices/{device_id}/resources/reconcile - device-Bearer-token
    gated (was internal-token-gated with no device scoping at all).'''

    def test_device_id_mismatch_is_not_found(self):
        request = _device_auth_request({"device_id": "some-other-device"}, body={"running_container_ids": []})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    def test_non_list_body_rejected(self):
        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": "not-a-list"})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

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

        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": ["c1", "c2"]})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
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

    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_running_pod_ips_repairs_stale_ip_address(self, mock_container_ops_cls, mock_device_ops_cls):
        '''Regression: containers.ip_address is only ever written once (on a successful
        CREATE/RESUME) - nothing re-syncs it if the pod is later recreated for any other reason.
        A real container hit this live: its stored ip_address was in a subnet no pod in that
        cluster has ever used, and socket-ssh kept hanging trying to reach it. This call must
        overwrite ip_address to the live pod_ip whenever they differ.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
            ip_address="10.43.209.155",
        ))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _device_auth_request({"device_id": DEVICE_A}, body={
            "running_container_ids": [CONTAINER_A], "running_pod_ips": {CONTAINER_A: "10.42.0.149"},
        })
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.update.assert_called_once_with({"id": CONTAINER_A}, {"ip_address": "10.42.0.149"})

    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_running_pod_ips_matching_current_ip_address_is_a_no_op(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
            ip_address="10.42.0.149",
        ))
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        request = _device_auth_request({"device_id": DEVICE_A}, body={
            "running_container_ids": [CONTAINER_A], "running_pod_ips": {CONTAINER_A: "10.42.0.149"},
        })
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_container_with_no_device_id_skipped(self, mock_container_ops_cls, mock_device_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(device_id=None))
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops_cls.return_value = mock_device_ops

        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": [CONTAINER_A]})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_device_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_container_belonging_to_a_different_device_is_skipped(self, mock_container_ops_cls, mock_device_ops_cls):
        '''Security regression guard: the old internal-token version trusted any container_id in
        the body regardless of which device it actually belonged to - safe only because that
        token was a fully-trusted global secret. A per-device Bearer token must not inherit that
        trust: a container belonging to a DIFFERENT device must be ignored, not reconciled.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id="some-other-device", cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
        ))
        mock_container_ops_cls.return_value = mock_ops
        mock_device_ops = MagicMock()
        mock_device_ops_cls.return_value = mock_device_ops

        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": [CONTAINER_A]})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_device_ops.update.assert_not_called()

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unknown_container_id_skipped(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": ["does-not-exist"]})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["reconciled_devices"], {})

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_empty_running_list_reconciles_nothing(self, mock_container_ops_cls):
        request = _device_auth_request({"device_id": DEVICE_A}, body={"running_container_ids": []})
        result = asyncio.run(container_handlers.reconcile_device_resources.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["reconciled_devices"], {})


def _running_row(container_id: str, updated_at, **overrides) -> dict:
    row = {
        "id": container_id, "user_id": USER_A, "device_id": DEVICE_A,
        "status": ContainerStatus.RUNNING.value, "updated_at": updated_at,
    }
    row.update(overrides)
    return row


class TestListActiveContainersForDevice(unittest.TestCase):
    '''
    Finishes Part 12: GET /devices/{device_id}/active-containers - status_monitor's periodic "does
    the DB think something is Running that I can't actually find a pod for" safety net, now
    device-Bearer-token gated instead of internal-token gated.
    '''

    def setUp(self) -> None:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        self.FRESH = (now - timedelta(seconds=5)).isoformat()   # inside the grace window
        self.OLD = (now - timedelta(seconds=200)).isoformat()   # well past the grace window

    def test_device_id_mismatch_is_not_found(self):
        request = _device_auth_request({"device_id": "some-other-device"})
        result = asyncio.run(container_handlers.list_active_containers_for_device.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_returns_running_containers_older_than_the_grace_window(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[_running_row("c1", self.OLD)])
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A})
        result = asyncio.run(container_handlers.list_active_containers_for_device.__wrapped__(request))

        self.assertEqual(result.status_code, 200)
        mock_ops.find.assert_called_once_with({"device_id": DEVICE_A, "status": ContainerStatus.RUNNING})
        import json
        self.assertEqual(json.loads(result.body)["container_ids"], ["c1"])

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_excludes_a_container_still_inside_the_grace_window(self, mock_container_ops_cls):
        '''A container that JUST became Running must not be flagged - status_monitor's own
        separately-fetched pod list may not show it yet purely from timing skew, not loss.'''
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[_running_row("c1", self.FRESH)])
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A})
        result = asyncio.run(container_handlers.list_active_containers_for_device.__wrapped__(request))

        import json
        self.assertEqual(json.loads(result.body)["container_ids"], [])

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_only_queries_this_devices_running_containers(self, mock_container_ops_cls):
        '''Ownership: the query itself is scoped to {device_id, status=Running} - PENDING/
        RESUMING/HIBERNATED rows and other devices' containers are never even fetched.'''
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[])
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": "device-b-id"}, device_id="device-b-id")
        asyncio.run(container_handlers.list_active_containers_for_device.__wrapped__(request))

        mock_ops.find.assert_called_once_with({"device_id": "device-b-id", "status": ContainerStatus.RUNNING})

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_no_running_containers_returns_empty_list(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[])
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A})
        result = asyncio.run(container_handlers.list_active_containers_for_device.__wrapped__(request))

        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["container_ids"], [])


class TestListIdleContainers(unittest.TestCase):
    '''Finishes Part 12: GET /devices/{device_id}/containers/idle, now device-Bearer-token gated.'''

    def test_device_id_mismatch_is_not_found(self):
        request = _device_auth_request(
            {"device_id": "some-other-device"}, device_id=DEVICE_A,
        )
        request.query_params = {"idle_threshold_seconds": "1800"}
        result = asyncio.run(container_handlers.list_idle_containers.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    def test_missing_threshold_rejected(self):
        request = _device_auth_request({"device_id": "device-a"}, device_id="device-a")
        request.query_params = {}
        result = asyncio.run(container_handlers.list_idle_containers.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

    def test_non_integer_threshold_rejected(self):
        request = _device_auth_request({"device_id": "device-a"}, device_id="device-a")
        request.query_params = {"idle_threshold_seconds": "not-a-number"}
        result = asyncio.run(container_handlers.list_idle_containers.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_scopes_query_to_the_given_device(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_idle_containers.return_value = OperationResult(success=True, data=[_container_row()])
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": "device-a"}, device_id="device-a")
        request.query_params = {"idle_threshold_seconds": "1800"}
        result = asyncio.run(container_handlers.list_idle_containers.__wrapped__(request))
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

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.DeviceCommandOps")
    @patch("src.cloud.container_handlers.DeviceOps")
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_hibernate_releases_unreleased_command_quota_too(
        self, mock_container_ops_cls, mock_device_ops_cls, mock_command_ops_cls,
    ):
        '''
        Same class of bug as delete_container's own regression test: an earlier CREATE/RESUME
        command for this container may hold a reservation that never got released (a lost
        CommandResult, or a status corrected by hand outside release_quota_for_command).
        Hibernate doesn't remove the container row, so there's no CASCADE data-loss risk the way
        delete has - but left unswept, it would sit stranded on the device for as long as the
        container stays hibernated, since nothing else ever looks at reserved_* here. hibernate
        must sweep it too, not just used_*.
        '''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row(
            device_id=DEVICE_A, cpu_limit="1", memory_limit="1Gi", storage_limit="2Gi",
        ))
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.update.return_value = OperationResult(success=True)
        mock_device_ops_cls.return_value = mock_device_ops

        mock_command_ops = MagicMock()
        mock_command_ops.find.return_value = OperationResult(success=True, data=[
            {"id": "cmd-stuck", "quota_reserved_cpu": 2, "quota_released_at": None},
        ])
        mock_command_ops.release_quota_for_command.return_value = OperationResult(success=True)
        mock_command_ops_cls.return_value = mock_command_ops

        request = _mock_request(path_params={"container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.hibernate_container(request))

        self.assertEqual(result.status_code, 200)
        mock_command_ops.release_quota_for_command.assert_called_once_with("cmd-stuck")


class TestGetContainerDevice(unittest.TestCase):
    '''Finishes Part 12: GET /devices/{device_id}/containers/{container_id} - replaces the old
    internal-token-gated GET /internal/containers/{container_id} container-maker's save() self-heal
    used; now device-Bearer-token gated and scoped to that device's own containers.'''

    def test_device_id_mismatch_is_not_found(self):
        request = _device_auth_request({"device_id": "some-other-device", "container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.get_container_device.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_unknown_container_404s(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.get_container_device.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_found_container_returned_scoped_by_device(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request({"device_id": DEVICE_A, "container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.get_container_device.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["container"]["id"], CONTAINER_A)
        mock_ops.find_one.assert_called_once_with({"id": CONTAINER_A, "device_id": DEVICE_A})


class TestUpdateContainerKubernetesIdDevice(unittest.TestCase):
    '''Finishes Part 12: POST /devices/{device_id}/containers/{container_id}/kubernetes-id -
    replaces container-maker's former use of the internal-token-gated POST /internal/containers/
    {container_id} for its kubernetes_id self-heal (containers.py's save()).'''

    def test_device_id_mismatch_is_not_found(self):
        request = _device_auth_request({"device_id": "some-other-device", "container_id": CONTAINER_A})
        result = asyncio.run(container_handlers.update_container_kubernetes_id_device.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    def test_missing_kubernetes_id_is_400(self):
        request = _device_auth_request({"device_id": DEVICE_A, "container_id": CONTAINER_A}, body={})
        result = asyncio.run(container_handlers.update_container_kubernetes_id_device.__wrapped__(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_container_not_owned_by_device_is_not_found(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request(
            {"device_id": DEVICE_A, "container_id": CONTAINER_A}, body={"kubernetes_id": "new-pod-uid"},
        )
        result = asyncio.run(container_handlers.update_container_kubernetes_id_device.__wrapped__(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_self_heal_updates_kubernetes_id(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request(
            {"device_id": DEVICE_A, "container_id": CONTAINER_A}, body={"kubernetes_id": "new-pod-uid"},
        )
        result = asyncio.run(container_handlers.update_container_kubernetes_id_device.__wrapped__(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.update.assert_called_once_with({"id": CONTAINER_A}, {"kubernetes_id": "new-pod-uid"})

    @patch("src.cloud.container_handlers.ContainerOps")
    def test_update_failure_returns_500(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_container_ops_cls.return_value = mock_ops

        request = _device_auth_request(
            {"device_id": DEVICE_A, "container_id": CONTAINER_A}, body={"kubernetes_id": "x"},
        )
        result = asyncio.run(container_handlers.update_container_kubernetes_id_device.__wrapped__(request))
        self.assertEqual(result.status_code, 500)


class TestUpdateContainerInternal(unittest.TestCase):
    '''save_reconciler.py's own stuck-save mark-failed path: POST /internal/containers/
    {container_id} - a strict field whitelist (save_status/save_error only, kubernetes_id removed
    once container-maker's own self-heal moved to update_container_kubernetes_id_device above),
    not a passthrough of the request body like the user-scoped update_container. Stays
    internal-token-gated: genuinely cluster-wide (every user's stuck saves), not one device's.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(path_params={"container_id": CONTAINER_A}, headers={})
        result = asyncio.run(container_handlers.update_container_internal(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_reconciler_updates_save_status_and_error(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(
            path_params={"container_id": CONTAINER_A},
            body={"save_status": "Failed", "save_error": "job disappeared"},
        )
        result = asyncio.run(container_handlers.update_container_internal(request))
        self.assertEqual(result.status_code, 200)
        mock_ops.update.assert_called_once_with(
            {"id": CONTAINER_A}, {"save_status": "Failed", "save_error": "job disappeared"}
        )

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_disallowed_fields_are_stripped_not_applied(self, mock_container_ops_cls):
        '''A caller trying to sneak status/device_id/kubernetes_id through this endpoint must be
        ignored - kubernetes_id now has its own dedicated, device-scoped endpoint, and
        status/device_id have their own dedicated, more carefully-guarded endpoints.'''
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=True)
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(
            path_params={"container_id": CONTAINER_A},
            body={"save_status": "Failed", "kubernetes_id": "sneaky", "status": "Deleted", "device_id": "sneaky"},
        )
        asyncio.run(container_handlers.update_container_internal(request))
        mock_ops.update.assert_called_once_with({"id": CONTAINER_A}, {"save_status": "Failed"})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_no_updatable_fields_is_400(self):
        request = _mock_request(path_params={"container_id": CONTAINER_A}, body={"status": "Deleted"})
        result = asyncio.run(container_handlers.update_container_internal(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_update_failure_returns_500(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.update.return_value = OperationResult(success=False, error="db down")
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request(path_params={"container_id": CONTAINER_A}, body={"save_status": "Failed"})
        result = asyncio.run(container_handlers.update_container_internal(request))
        self.assertEqual(result.status_code, 500)


class TestListStuckSaves(unittest.TestCase):
    '''container-maker's save_reconciler off-direct-Postgres migration:
    GET /internal/containers/stuck-saves.'''

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request(headers={})
        result = asyncio.run(container_handlers.list_stuck_saves(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_returns_rows_across_all_users(self, mock_container_ops_cls):
        rows = [
            _container_row(id="c1", user_id="user-a", save_status="Pending"),
            _container_row(id="c2", user_id="user-b", save_status="Running"),
        ]
        mock_ops = MagicMock()
        mock_ops.find_stuck_saves.return_value = OperationResult(success=True, data=rows)
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request()
        result = asyncio.run(container_handlers.list_stuck_saves(request))
        self.assertEqual(result.status_code, 200)
        import json
        body = json.loads(result.body)
        self.assertEqual(len(body["containers"]), 2)
        self.assertEqual({c["user_id"] for c in body["containers"]}, {"user-a", "user-b"})

    @patch("src.cloud.container_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.container_handlers.ContainerOps")
    def test_query_failure_returns_500(self, mock_container_ops_cls):
        mock_ops = MagicMock()
        mock_ops.find_stuck_saves.return_value = OperationResult(success=False, error="db down")
        mock_container_ops_cls.return_value = mock_ops

        request = _mock_request()
        result = asyncio.run(container_handlers.list_stuck_saves(request))
        self.assertEqual(result.status_code, 500)


if __name__ == "__main__":
    unittest.main()
