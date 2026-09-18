'''
remotetunelling.md Phase 5/7 - terminal ticket lifecycle tests.

create_terminal_session is internal-token-gated (mocked the same way as every other container
write route - see test_container_api.py); consume_terminal_session is Bearer-device-token-gated,
tested the same "call the undecorated handler with request.state pre-set" way test_device_api.py
already establishes for authenticate_device.
'''
import asyncio
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult

import src.cloud.terminal_handlers as terminal_handlers

USER_A = "user-a"
DEVICE_A = "device-a-id"
DEVICE_B = "device-b-id"
CONTAINER_A = "container-a-id"


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _internal_request(container_id: str = CONTAINER_A, user_id: str = USER_A, token: str = "internal-token") -> MagicMock:
    request = MagicMock(spec=Request)
    request.path_params = {"container_id": container_id}
    request.headers = {"X-Internal-Service-Token": token}
    request.json = _async_return({"user_id": user_id})
    return request


def _device_request(body: dict, device_id: str = DEVICE_A, user_id: str = USER_A) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body)
    request.state.user_id = user_id
    request.state.device_id = device_id
    request.state.scopes = []
    return request


def _container_row(**overrides) -> dict:
    row = {
        "id": CONTAINER_A,
        "user_id": USER_A,
        "device_id": DEVICE_A,
        "status": "Running",
        "ip_address": "10.42.0.5",
        "port_mappings": [{"publish_port": 2222, "target_port": 22, "protocol": "TCP"}],
        "environment_vars": {"SSH_USERNAME": "u", "SSH_PASSWORD": "p"},
    }
    row.update(overrides)
    return row


def _device_row(**overrides) -> dict:
    row = {
        "id": DEVICE_A,
        "user_id": USER_A,
        "status": "Active",
        "tunnel_status": "Online",
        "tunnel_public_url": "https://abcd.ngrok-free.app",
        "tunnel_last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


class TestCreateTerminalSession(TestCase):
    def test_missing_internal_token_rejected(self) -> None:
        request = _internal_request(token="wrong")
        with patch("src.cloud.terminal_handlers.CLOUD_INTERNAL_API_TOKEN", "internal-token"):
            result = asyncio.run(terminal_handlers.create_terminal_session(request))
        self.assertEqual(result.status_code, 401)

    def test_owner_gets_a_ticket_and_wss_url_for_a_running_container_on_an_online_device(self) -> None:
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(success=True, data=_device_row())

        request = _internal_request()
        with patch("src.cloud.terminal_handlers.CLOUD_INTERNAL_API_TOKEN", "internal-token"), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops), \
             patch("src.cloud.terminal_handlers.DeviceOps", return_value=mock_device_ops):
            result = asyncio.run(terminal_handlers.create_terminal_session(request))

        self.assertEqual(result.status_code, 200)
        import json
        payload = json.loads(result.body)
        self.assertEqual(payload["websocket_url"], "wss://abcd.ngrok-free.app")
        self.assertTrue(len(payload["ticket"]) > 20)

    def test_container_not_running_rejected(self) -> None:
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(
            success=True, data=_container_row(status="Hibernated")
        )
        request = _internal_request()
        with patch("src.cloud.terminal_handlers.CLOUD_INTERNAL_API_TOKEN", "internal-token"), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops):
            result = asyncio.run(terminal_handlers.create_terminal_session(request))
        self.assertEqual(result.status_code, 409)

    def test_offline_device_rejected(self) -> None:
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())
        mock_device_ops = MagicMock()
        mock_device_ops.find_one.return_value = OperationResult(
            success=True,
            data=_device_row(tunnel_last_heartbeat_at=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()),
        )
        request = _internal_request()
        with patch("src.cloud.terminal_handlers.CLOUD_INTERNAL_API_TOKEN", "internal-token"), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops), \
             patch("src.cloud.terminal_handlers.DeviceOps", return_value=mock_device_ops):
            result = asyncio.run(terminal_handlers.create_terminal_session(request))
        self.assertEqual(result.status_code, 409)

    def test_another_users_container_is_not_found(self) -> None:
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=None)
        request = _internal_request(user_id="user-b")
        with patch("src.cloud.terminal_handlers.CLOUD_INTERNAL_API_TOKEN", "internal-token"), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops):
            result = asyncio.run(terminal_handlers.create_terminal_session(request))
        self.assertEqual(result.status_code, 404)


class TestConsumeTerminalSession(TestCase):
    def test_valid_ticket_returns_connection_info(self) -> None:
        mock_ticket_manager = MagicMock()
        mock_ticket_manager.consume_ticket.return_value = {
            "user_id": USER_A, "device_id": DEVICE_A, "container_id": CONTAINER_A,
        }
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())

        request = _device_request({"ticket": "real-ticket"}, device_id=DEVICE_A)
        with patch("src.cloud.terminal_handlers.TerminalTicketManager", return_value=mock_ticket_manager), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops):
            result = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(request=request))

        self.assertEqual(result.status_code, 200)
        import json
        payload = json.loads(result.body)
        self.assertEqual(payload["ssh_host"], "10.42.0.5")
        self.assertEqual(payload["ssh_port"], 22)
        self.assertEqual(payload["ssh_username"], "u")

    def test_missing_or_expired_ticket_rejected(self) -> None:
        mock_ticket_manager = MagicMock()
        mock_ticket_manager.consume_ticket.return_value = None
        request = _device_request({"ticket": "gone"}, device_id=DEVICE_A)
        with patch("src.cloud.terminal_handlers.TerminalTicketManager", return_value=mock_ticket_manager):
            result = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(request=request))
        self.assertEqual(result.status_code, 401)

    def test_ticket_replay_is_rejected(self) -> None:
        '''consume_ticket is GETDEL-atomic - a second call for the same ticket must see None,
        exactly like the missing/expired case (Redis already guarantees this; this test locks in
        that the handler doesn't add its own accidental second chance for it).'''
        mock_ticket_manager = MagicMock()
        mock_ticket_manager.consume_ticket.side_effect = [
            {"user_id": USER_A, "device_id": DEVICE_A, "container_id": CONTAINER_A}, None,
        ]
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(success=True, data=_container_row())

        with patch("src.cloud.terminal_handlers.TerminalTicketManager", return_value=mock_ticket_manager), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops):
            first = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(
                request=_device_request({"ticket": "t"}, device_id=DEVICE_A)
            ))
            second = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(
                request=_device_request({"ticket": "t"}, device_id=DEVICE_A)
            ))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)

    def test_wrong_device_cannot_consume_anothers_ticket(self) -> None:
        mock_ticket_manager = MagicMock()
        mock_ticket_manager.consume_ticket.return_value = {
            "user_id": USER_A, "device_id": DEVICE_A, "container_id": CONTAINER_A,
        }
        request = _device_request({"ticket": "real-ticket"}, device_id=DEVICE_B)
        with patch("src.cloud.terminal_handlers.TerminalTicketManager", return_value=mock_ticket_manager):
            result = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(request=request))
        self.assertEqual(result.status_code, 401)

    def test_container_no_longer_running_rejected(self) -> None:
        mock_ticket_manager = MagicMock()
        mock_ticket_manager.consume_ticket.return_value = {
            "user_id": USER_A, "device_id": DEVICE_A, "container_id": CONTAINER_A,
        }
        mock_container_ops = MagicMock()
        mock_container_ops.find_one.return_value = OperationResult(
            success=True, data=_container_row(status="Hibernated")
        )
        request = _device_request({"ticket": "real-ticket"}, device_id=DEVICE_A)
        with patch("src.cloud.terminal_handlers.TerminalTicketManager", return_value=mock_ticket_manager), \
             patch("src.cloud.terminal_handlers.ContainerOps", return_value=mock_container_ops):
            result = asyncio.run(terminal_handlers.consume_terminal_session.__wrapped__(request=request))
        self.assertEqual(result.status_code, 409)


if __name__ == "__main__":
    import unittest
    unittest.main()
