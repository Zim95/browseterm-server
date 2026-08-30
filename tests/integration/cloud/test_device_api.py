'''
P05 -- Device Cloud API tests.

Same "mock the boundary" convention as
`tests/integration/containers/test_ownership_idor.py`: call the UNDECORATED handler via
`<handler>.__wrapped__` (skips the real Redis session lookup -- `authenticate_session` normally
sets `request.state.user_info` from a validated session, which the mock `Request` below stands
in for directly) and patch `DeviceOps` at its import site in `src.cloud.device_handlers`, so no
live Postgres/Redis is touched.

Covers every case in p05.md's required test list except revoke (not part of P05's scope per the
authoritative plan's Section 22 -- P05 is register/read/update metadata/update
allocation/heartbeat only).
'''
import asyncio
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import Request
from fastapi.testclient import TestClient

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations import OperationResult
from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel

import app as cloud_app
import src.cloud.device_handlers as device_handlers

USER_A = "user-a"
USER_B = "user-b"
DEVICE_A = "device-a-id"
DEVICE_B = "device-b-id"


def _mock_request(body: dict = None, path_params: dict = None, user_id: str = USER_A) -> MagicMock:
    '''A FastAPI Request stand-in carrying an authenticated identity, as @authenticate_session
    would set it (request.state.user_info is a plain dict -- see session_dto.SessionDataModel).'''
    request = MagicMock(spec=Request)
    request.json = _async_return(body or {})
    request.path_params = path_params or {}
    request.state.user_info = {"id": user_id}
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


class TestRegisterDeviceOwnership(TestCase):
    '''POST /devices'''

    def test_authenticated_user_can_register_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.insert.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(
            body={
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "runtime_version": "1.0.0",
                "total_cpu": 8, "total_memory_bytes": 16_000_000_000, "total_storage_bytes": 500_000_000_000,
                "allocated_cpu": 6, "allocated_memory_bytes": 8_000_000_000, "allocated_storage_bytes": 100_000_000_000,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 201)
        self.assertEqual(mock_ops.insert.call_args.args[0]["user_id"], USER_A)

    def test_server_controls_user_id_not_client(self) -> None:
        '''Body has no user_id field at all -- RegisterDeviceRequest doesn't declare one.'''
        mock_ops = MagicMock()
        mock_ops.insert.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(
            body={
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "total_cpu": 8, "total_memory_bytes": 16, "total_storage_bytes": 16,
                "allocated_cpu": 4, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        self.assertEqual(mock_ops.insert.call_args.args[0]["user_id"], USER_A)

    def test_spoofed_body_user_id_cannot_register_for_another_user(self) -> None:
        mock_ops = MagicMock()
        mock_ops.insert.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(
            body={
                "user_id": USER_B,  # attacker spoofs another user's id
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "total_cpu": 8, "total_memory_bytes": 16, "total_storage_bytes": 16,
                "allocated_cpu": 4, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        called_user_id = mock_ops.insert.call_args.args[0]["user_id"]
        self.assertEqual(called_user_id, USER_A)
        self.assertNotEqual(called_user_id, USER_B)

    def test_allocation_exceeding_total_is_rejected(self) -> None:
        mock_ops = MagicMock()
        request = _mock_request(
            body={
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "total_cpu": 4, "total_memory_bytes": 16, "total_storage_bytes": 16,
                "allocated_cpu": 8, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 400)
        mock_ops.insert.assert_not_called()

    def test_negative_resource_values_rejected(self) -> None:
        mock_ops = MagicMock()
        request = _mock_request(
            body={
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "total_cpu": -1, "total_memory_bytes": 16, "total_storage_bytes": 16,
                "allocated_cpu": 0, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 400)
        mock_ops.insert.assert_not_called()

    def test_duplicate_registration_returns_conflict(self) -> None:
        mock_ops = MagicMock()
        mock_ops.insert.return_value = OperationResult(
            success=False, error="User not found or device name already registered for this user"
        )
        request = _mock_request(
            body={
                "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                "total_cpu": 8, "total_memory_bytes": 16, "total_storage_bytes": 16,
                "allocated_cpu": 4, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
            },
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.register_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 409)


class TestListDevicesOwnership(TestCase):
    '''GET /devices'''

    def test_user_sees_own_devices(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[_device_row()])
        request = _mock_request(user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.list_devices.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_ops.find.call_args.args[0], {"user_id": USER_A})

    def test_user_does_not_see_another_users_devices(self) -> None:
        '''The list filter must be scoped to the caller's own user_id, never another's.'''
        mock_ops = MagicMock()
        mock_ops.find.return_value = OperationResult(success=True, data=[])
        request = _mock_request(user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            asyncio.run(device_handlers.list_devices.__wrapped__(request=request))
        filters = mock_ops.find.call_args.args[0]
        self.assertEqual(filters, {"user_id": USER_A})
        self.assertNotEqual(filters.get("user_id"), USER_B)


class TestGetDeviceOwnership(TestCase):
    '''GET /devices/{device_id}'''

    def test_owner_can_get_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_device_row())
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_ops.find_one.call_args.args[0], {"id": DEVICE_A, "user_id": USER_A})

    def test_non_owner_cannot_get_device(self) -> None:
        mock_ops = MagicMock()
        # Real DeviceOps.find_one with an {"id": DEVICE_B, "user_id": USER_A} filter would find
        # no matching row -- USER_A does not own DEVICE_B.
        mock_ops.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        self.assertEqual(mock_ops.find_one.call_args.args[0], {"id": DEVICE_B, "user_id": USER_A})

    def test_nonexistent_device_matches_same_not_found_response(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        request = _mock_request(path_params={"device_id": "does-not-exist"}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            not_found_result = asyncio.run(device_handlers.get_device.__wrapped__(request=request))

        mock_ops2 = MagicMock()
        mock_ops2.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        other_owner_request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops2):
            other_owner_result = asyncio.run(device_handlers.get_device.__wrapped__(request=other_owner_request))

        self.assertEqual(not_found_result.status_code, other_owner_result.status_code)
        self.assertEqual(not_found_result.body, other_owner_result.body)


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
            body={"device_name": "renamed"},
            path_params={"device_id": DEVICE_A},
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(update_data, {"device_name": "renamed"})

    def test_non_owner_cannot_update_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        request = _mock_request(
            body={"device_name": "renamed"},
            path_params={"device_id": DEVICE_B},
            user_id=USER_A,
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
                "id": "attacker-chosen-id",
                "user_id": USER_B,
                "used_cpu": 999,
                "used_memory_bytes": 999,
                "used_storage_bytes": 999,
                "status": "Revoked",
                "registered_at": "2000-01-01T00:00:00",
                "revoked_at": "2000-01-01T00:00:00",
                "runtime_version": "2.0.0",  # the one allowed field in this body
            },
            path_params={"device_id": DEVICE_A},
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.update_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertEqual(update_data, {"runtime_version": "2.0.0"})

    def test_invalid_resulting_allocation_is_rejected(self) -> None:
        '''existing total_cpu=8/allocated_cpu=6; lowering total_cpu to 4 without also lowering
        allocated_cpu must fail -- validation must use existing AND incoming values together.'''
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=_device_row(total_cpu=8, allocated_cpu=6))
        request = _mock_request(
            body={"total_cpu": 4},
            path_params={"device_id": DEVICE_A},
            user_id=USER_A,
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
        before = datetime.now(timezone.utc)
        request = _mock_request(path_params={"device_id": DEVICE_A}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        after = datetime.now(timezone.utc)

        self.assertEqual(result.status_code, 200)
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertEqual(update_filters, {"id": DEVICE_A, "user_id": USER_A})
        self.assertIn("last_seen_at", update_data)
        self.assertIsInstance(update_data["last_seen_at"], datetime)
        self.assertTrue(before <= update_data["last_seen_at"] <= after)
        self.assertEqual(update_data["status"], DeviceStatus.ACTIVE)

    def test_non_owner_cannot_heartbeat_device(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.return_value = OperationResult(success=True, data=None, message="Device not found")
        request = _mock_request(path_params={"device_id": DEVICE_B}, user_id=USER_A)
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            result = asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        self.assertEqual(result.status_code, 404)
        mock_ops.update.assert_not_called()

    def test_client_cannot_spoof_last_seen_at(self) -> None:
        mock_ops = MagicMock()
        mock_ops.find_one.side_effect = [
            OperationResult(success=True, data=_device_row()),
            OperationResult(success=True, data=_device_row()),
        ]
        mock_ops.update.return_value = OperationResult(success=True)
        spoofed = "2000-01-01T00:00:00+00:00"
        request = _mock_request(
            body={"last_seen_at": spoofed},
            path_params={"device_id": DEVICE_A},
            user_id=USER_A,
        )
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_ops):
            asyncio.run(device_handlers.heartbeat_device.__wrapped__(request=request))
        update_filters, update_data = mock_ops.update.call_args.args
        self.assertIsInstance(update_data["last_seen_at"], datetime)
        self.assertNotEqual(update_data["last_seen_at"].isoformat(), spoofed)


class TestDeviceApiRouting(TestCase):
    '''
    End-to-end sanity check through the real `cloud_app` FastAPI app -- proves the routes are
    wired to the right methods/paths AND that `@authenticate_session` (the real decorator, not
    `__wrapped__`) accepts a genuinely valid session cookie and rejects a missing one, unlike the
    handler-level tests above which bypass the decorator entirely. Only `RedisSessionManager`
    (session validation) and `DeviceOps` (DB) are mocked -- no live Redis/Postgres.
    '''

    def setUp(self) -> None:
        self.client = TestClient(cloud_app.app)

    def _valid_session_manager(self, user_id: str) -> MagicMock:
        manager = MagicMock()
        manager.validate_session.return_value = SessionValidationModel(
            is_valid=True,
            session_data=SessionDataModel(
                user_info={"id": user_id}, subscription_info={}, current_subscription_plan={}
            ),
            ttl=1800,
        )
        return manager

    def test_register_and_get_round_trip_through_real_routing(self) -> None:
        mock_device_ops = MagicMock()
        mock_device_ops.insert.return_value = OperationResult(success=True, data=_device_row())
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())

        self.client.cookies.set("session", "valid-session-id")
        with patch(
            "src.authentication.authentication_helpers.RedisSessionManager",
            return_value=self._valid_session_manager(USER_A),
        ), patch("src.cloud.device_handlers.DeviceOps", return_value=mock_device_ops):
            register_response = self.client.post(
                "/devices",
                json={
                    "device_name": "macbook", "os": "macOS", "architecture": "arm64",
                    "total_cpu": 8, "total_memory_bytes": 16, "total_storage_bytes": 16,
                    "allocated_cpu": 4, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
                },
            )
            get_response = self.client.get(f"/devices/{DEVICE_A}")

        self.assertEqual(register_response.status_code, 201)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["device"]["id"], DEVICE_A)

    def test_missing_session_cookie_is_rejected_before_reaching_the_handler(self) -> None:
        mock_device_ops = MagicMock()
        with patch("src.cloud.device_handlers.DeviceOps", return_value=mock_device_ops):
            response = self.client.get(f"/devices/{DEVICE_A}", follow_redirects=False)
        # @authenticate_session redirects unauthenticated requests (same as every other
        # existing session-protected endpoint in this codebase -- see src/api_handlers.py).
        self.assertEqual(response.status_code, 302)
        mock_device_ops.find_one.assert_not_called()
