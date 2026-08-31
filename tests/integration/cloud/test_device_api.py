'''
P05/P07 -- Device Cloud API tests.

P07 change: these routes are now device-token (Bearer) authenticated instead of session-cookie
authenticated (p07.md section 16/20) - `_mock_request` below sets `request.state.user_id`/
`device_id`/`scopes` the way the real `authenticate_device` decorator would after validating a
token, and handler-level tests call `<handler>.__wrapped__` to bypass that decorator entirely
(same "mock the boundary" convention as before). `TestDeviceApiRouting` exercises the real
decorator via `Authorization: Bearer` + a mocked `DeviceTokenManager`.

Registration (`POST /devices`) no longer exists as a standalone route -- see
`test_oauth_handlers.py`'s `TestDeviceBootstrapRedeem` for register/re-activate/token-issuance
coverage (that's the only path that can create a device now, per p07.md section 21).
'''
import asyncio
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import Request
from fastapi.testclient import TestClient

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations import OperationResult

import app as cloud_app
import src.cloud.device_handlers as device_handlers

USER_A = "user-a"
USER_B = "user-b"
DEVICE_A = "device-a-id"
DEVICE_B = "device-c-id"


def _mock_request(body: dict = None, path_params: dict = None, user_id: str = USER_A, device_id: str = DEVICE_A) -> MagicMock:
    '''A FastAPI Request stand-in carrying an authenticated device identity, as
    @authenticate_device would set it after validating a Bearer token.'''
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {}
    request.state.user_id = user_id
    request.state.device_id = device_id
    request.state.scopes = ["device:read", "device:update", "device:heartbeat"]
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _device_row(**overrides) -> dict:
    row = {
        "id": DEVICE_A,
        "user_id": USER_A,
        "device_name": "macbook",
        "os": "macOS",
        "architecture": "arm64",
        "runtime_version": "1.0.0",
        "total_cpu": 8,
        "total_memory_bytes": 16_000_000_000,
        "total_storage_bytes": 500_000_000_000,
        "allocated_cpu": 6,
        "allocated_memory_bytes": 8_000_000_000,
        "allocated_storage_bytes": 100_000_000_000,
        "used_cpu": 0,
        "used_memory_bytes": 0,
        "used_storage_bytes": 0,
        "gpu_info": None,
        "status": "Active",
        "registered_at": "2026-01-01T00:00:00+00:00",
        "last_seen_at": None,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "revoked_at": None,
    }
    row.update(overrides)
    return row


class TestListDevicesOwnership(TestCase):
    '''GET /devices -- returns only the token's own device (p07.md section 16-18).'''

    def test_returns_only_the_tokens_own_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.list_devices.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_ops.find_one.call_args.args[0], {"id": DEVICE_A, "user_id": USER_A})

    def test_missing_device_returns_empty_list_not_error(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None)
        request = _mock_request(user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.list_devices.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, b'{"devices":[]}')


class TestGetDeviceOwnership(TestCase):
    '''GET /devices/{device_id}'''

    def test_own_device_token_can_get_its_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)

    def test_d1_token_cannot_operate_as_d2(self) -> None:
        '''p07.md section 18: T1 must not operate as D2 -- path device_id != token's own
        device_id is rejected before any DB lookup even happens.'''
        mock_ops = MagicMock()
        request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_ops.find_one.assert_not_called()

    def test_nonexistent_device_matches_same_not_found_response_as_mismatched_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            not_found_result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))

        mismatch_request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A, device_id=DEVICE_A)
        mismatch_result = asyncio.run(device_handlers.get_device.__wrapped__(request=mismatch_request))

        self.assertEqual(not_found_result.status_code, mismatch_result.status_code)
        self.assertEqual(not_found_result.body, mismatch_result.body)


class TestUpdateDeviceOwnership(TestCase):
    '''POST /devices/{device_id}'''

    def test_owner_can_update_allowed_fields(self) -> None:
        mock_ops = MagicMock()
        updated_row = _device_row(device_name="renamed")
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_device_row()),
            OperationResult(success=True, data=updated_row),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        request = _mock_request(
            body={"device_name": "renamed"}, path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(update_data, {"device_name": "renamed"})

    def test_d1_token_cannot_update_d2(self) -> None:
        mock_ops = MagicMock()
        request = _mock_request(
            body={"device_name": "renamed"}, path_params={"device_id": DEVICE_B}, user_id=USER_A, device_id=DEVICE_A
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_ops.update.assert_not_called()

    def test_protected_fields_cannot_be_overwritten(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_device_row()),
            OperationResult(success=True, data=_device_row()),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        request = _mock_request(
            body={
                "id": "attacker-chosen-id", "user_id": USER_B, "used_cpu": 999, "status": "Revoked",
                "runtime_version": "2.0.0",
            },
            path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(update_data, {"runtime_version": "2.0.0"})

    def test_invalid_resulting_allocation_is_rejected(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_device_row(total_cpu=8, allocated_cpu=6))
        request = _mock_request(
            body={"total_cpu": 4}, path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 400)
        mock_ops.update.assert_not_called()


class TestHeartbeatDeviceOwnership(TestCase):
    '''POST /devices/{device_id}/heartbeat'''

    def test_owner_heartbeat_updates_last_seen_at_and_status(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_device_row(last_seen_at=None)),
            OperationResult(success=True, data=_device_row(last_seen_at="2026-08-30T12:00:00+00:00")),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.find.return_value = OperationResult(success=True, data=[])
        before = datetime.now(timezone.utc)
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        after = datetime.now(timezone.utc)

        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertIsInstance(update_data["last_seen_at"], datetime)
        self.assertTrue(before <= update_data["last_seen_at"] <= after)
        self.assertEqual(update_data["status"], DeviceStatus.ACTIVE)

    def test_d1_token_cannot_heartbeat_d2(self) -> None:
        mock_ops = MagicMock()
        request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_ops.update.assert_not_called()

    def test_heartbeat_demotes_the_users_other_active_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_device_row(id=DEVICE_A)),
            OperationResult(success=True, data=_device_row(id=DEVICE_A, status=DeviceStatus.ACTIVE)),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        mock_ops.find.return_value = OperationResult(
            success=True,
            data=[
                _device_row(id=DEVICE_A, status=DeviceStatus.ACTIVE),
                _device_row(id="device-sibling-id", user_id=USER_A, status=DeviceStatus.ACTIVE),
            ],
        )
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A, device_id=DEVICE_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        mock_ops.update.assert_called_with(
            {"id": "device-sibling-id", "user_id": USER_A}, {"status": DeviceStatus.INACTIVE}
        )


class TestDeviceApiRouting(TestCase):
    '''
    End-to-end sanity check through the real FastAPI app -- proves routes are wired correctly AND
    that the real `authenticate_device` decorator accepts a valid Bearer token and rejects a
    missing/invalid one, unlike the handler-level tests above which bypass it via `__wrapped__`.
    '''

    def setUp(self) -> None:
        self.client = TestClient(cloud_app.app, base_url="http://testserver")

    def test_valid_bearer_token_reaches_the_handler(self) -> None:
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        mock_token_manager = MagicMock()
        mock_token_manager.validate_token.return_value = {
            "user_id": USER_A, "device_id": DEVICE_A, "scopes": ["device:read"]
        }
        with patch("src.cloud.device_handlers.DeviceTokenManager", return_value=mock_token_manager), \
             patch("src.cloud.device_handlers.DeviceOps", return_value=mock_device_ops):
            response = self.client.get(f"/devices/{DEVICE_A}", headers={"Authorization": "Bearer bst_device_valid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["device"]["id"], DEVICE_A)

    def test_missing_bearer_token_is_rejected_before_reaching_the_handler(self) -> None:
        mock_device_ops = MagicMock()
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_device_ops):
            response = self.client.get(f"/devices/{DEVICE_A}")
        self.assertEqual(response.status_code, 401)
        mock_device_ops.find_one.assert_not_called()

    def test_invalid_bearer_token_is_rejected(self) -> None:
        mock_token_manager = MagicMock()
        mock_token_manager.validate_token.return_value = None
        with patch("src.cloud.device_handlers.DeviceTokenManager", return_value=mock_token_manager):
            response = self.client.get(f"/devices/{DEVICE_A}", headers={"Authorization": "Bearer bst_device_bogus"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    import unittest
    unittest.main()
