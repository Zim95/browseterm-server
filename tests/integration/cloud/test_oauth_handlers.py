'''
P07 -- Cloud OAuth start/callback, handoff redemption, and device-bootstrap tests. Same
"mock the boundary" convention as test_auth_api.py/test_device_api.py: call handlers directly,
patch Redis-touching managers and the provider HTTP call at their import site in
src.cloud.oauth_handlers.
'''
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import Request

import src.cloud.oauth_handlers as oauth_handlers
from src.authentication.dto.session_dto import SessionResponseModel
from browseterm_db.operations import OperationResult

TOKEN = "test-internal-token"


def _mock_request(query_params: dict = None, body: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.query_params = query_params or {}
    request.path_params = {}
    request.json = _async_return(body if body is not None else {})
    request.headers = headers if headers is not None else {}
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


class TestOAuthStart(unittest.TestCase):
    def test_unsupported_provider_rejected(self):
        request = _mock_request()
        request.path_params = {"provider": "facebook"}
        result = asyncio.run(oauth_handlers.oauth_start(request))
        self.assertEqual(result.status_code, 400)

    def test_unsupported_target_rejected(self):
        request = _mock_request(query_params={"target": "attacker-controlled"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_start(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.oauth_handlers.OAuthStateManager")
    def test_valid_start_redirects_to_provider_with_state(self, mock_state_cls):
        mock_state_cls.return_value.create_state.return_value = "random-state-value"
        request = _mock_request(query_params={"target": "local"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_start(request))
        self.assertEqual(result.status_code, 302)
        location = result.headers["location"]
        self.assertTrue(location.startswith("https://accounts.google.com/"))
        qs = parse_qs(urlparse(location).query)
        self.assertEqual(qs["state"], ["random-state-value"])
        mock_state_cls.return_value.create_state.assert_called_once_with("google", "local")


class TestOAuthCallback(unittest.TestCase):
    def test_provider_error_redirects_to_login_with_error(self):
        request = _mock_request(query_params={"error": "access_denied"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))
        self.assertEqual(result.status_code, 302)
        self.assertIn("auth_result=error", result.headers["location"])

    def test_missing_code_or_state_rejected(self):
        request = _mock_request(query_params={"code": "abc"})  # no state
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))
        self.assertIn("auth_result=error", result.headers["location"])

    @patch("src.cloud.oauth_handlers.OAuthStateManager")
    def test_invalid_or_expired_state_rejected(self, mock_state_cls):
        mock_state_cls.return_value.consume_state.return_value = None
        request = _mock_request(query_params={"code": "abc", "state": "bogus"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))
        self.assertIn("auth_result=error", result.headers["location"])

    @patch("src.cloud.oauth_handlers.HandoffManager")
    @patch("src.cloud.oauth_handlers.process_user_info", new_callable=AsyncMock)
    @patch("src.cloud.oauth_handlers.PROVIDER_SERVICES")
    @patch("src.cloud.oauth_handlers.OAuthStateManager")
    def test_valid_callback_creates_session_and_redirects_with_handoff(
        self, mock_state_cls, mock_provider_services, mock_process_user_info, mock_handoff_cls
    ):
        mock_state_cls.return_value.consume_state.return_value = {"provider": "google", "target": "local"}
        mock_service_instance = MagicMock()
        mock_service_instance.fetch_user_info = AsyncMock(return_value=MagicMock())
        mock_provider_services.__contains__.return_value = True
        mock_provider_services.__getitem__.return_value = lambda: mock_service_instance
        mock_process_user_info.return_value = SessionResponseModel(
            session_id="s1", user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}
        )
        mock_handoff_cls.return_value.create_handoff.return_value = "handoff-code-1"

        request = _mock_request(query_params={"code": "provider-code", "state": "valid-state"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))

        self.assertEqual(result.status_code, 302)
        qs = parse_qs(urlparse(result.headers["location"]).query)
        self.assertEqual(qs["code"], ["handoff-code-1"])
        mock_handoff_cls.return_value.create_handoff.assert_called_once_with("local_login", "u1", "s1")

    def test_never_redirects_to_an_attacker_supplied_destination(self):
        '''p07.md section 10: the destination is always the server-configured
        BROWSETERM_LOCAL_CALLBACK_URL / _TARGET_CALLBACKS mapping, never taken from any
        request-supplied value -- there is no redirect_uri/target read from the callback request
        at all that could steer the final redirect elsewhere.'''
        import inspect
        source = inspect.getsource(oauth_handlers.oauth_callback)
        self.assertNotIn("request.query_params.get(\"redirect_uri\")", source)
        self.assertNotIn("request.query_params.get(\"target\")", source)


class TestHandoffRedeem(unittest.TestCase):
    def test_missing_code_rejected(self):
        request = _mock_request(body={})
        result = asyncio.run(oauth_handlers.handoff_redeem(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_invalid_or_expired_handoff_rejected(self, mock_handoff_cls):
        mock_handoff_cls.return_value.consume_handoff.return_value = None
        request = _mock_request(body={"code": "bogus"})
        result = asyncio.run(oauth_handlers.handoff_redeem(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.oauth_handlers.RedisSessionManager")
    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_valid_handoff_returns_session(self, mock_handoff_cls, mock_session_cls):
        from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel
        mock_handoff_cls.return_value.consume_handoff.return_value = {
            "purpose": "local_login", "user_id": "u1", "session_id": "s1",
        }
        mock_session_cls.return_value.validate_session.return_value = SessionValidationModel(
            is_valid=True,
            session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
        )
        request = _mock_request(body={"code": "valid-code"})
        result = asyncio.run(oauth_handlers.handoff_redeem(request))
        self.assertEqual(result.status_code, 200)
        import json
        self.assertEqual(json.loads(result.body)["session_id"], "s1")

    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_second_redemption_fails(self, mock_handoff_cls):
        '''consume_handoff is GETDEL-based (single-use) -- the second call for the same code
        returns None from Redis, exactly like this mock does.'''
        mock_handoff_cls.return_value.consume_handoff.side_effect = [
            {"purpose": "local_login", "user_id": "u1", "session_id": "s1"}, None,
        ]
        request = _mock_request(body={"code": "one-time-code"})
        with patch("src.cloud.oauth_handlers.RedisSessionManager") as mock_session_cls:
            from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel
            mock_session_cls.return_value.validate_session.return_value = SessionValidationModel(
                is_valid=True,
                session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
            )
            first = asyncio.run(oauth_handlers.handoff_redeem(request))
            second = asyncio.run(oauth_handlers.handoff_redeem(request))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)


class TestDeviceBootstrapStart(unittest.TestCase):
    def test_missing_internal_token_rejected(self):
        request = _mock_request(body={"user_id": "u1"}, headers={})
        result = asyncio.run(oauth_handlers.device_bootstrap_start(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.oauth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_valid_request_returns_bootstrap_code(self, mock_handoff_cls):
        mock_handoff_cls.return_value.create_handoff.return_value = "bootstrap-code-1"
        request = _mock_request(body={"user_id": "u1"}, headers={"X-Internal-Service-Token": TOKEN})
        result = asyncio.run(oauth_handlers.device_bootstrap_start(request))
        self.assertEqual(result.status_code, 200)
        mock_handoff_cls.return_value.create_handoff.assert_called_once_with("device_bootstrap", "u1")


class TestDeviceBootstrapRedeem(unittest.TestCase):
    _DEVICE_BODY = {
        "device_name": "macbook", "os": "macOS", "architecture": "arm64",
        "total_cpu": 8, "total_memory_bytes": 16, "total_storage_bytes": 16,
        "allocated_cpu": 4, "allocated_memory_bytes": 8, "allocated_storage_bytes": 8,
    }

    def test_missing_code_or_device_rejected(self):
        request = _mock_request(body={"code": "x"})  # no device
        result = asyncio.run(oauth_handlers.device_bootstrap_redeem(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_invalid_bootstrap_code_rejected(self, mock_handoff_cls):
        mock_handoff_cls.return_value.consume_handoff.return_value = None
        request = _mock_request(body={"code": "bogus", "device": self._DEVICE_BODY})
        result = asyncio.run(oauth_handlers.device_bootstrap_redeem(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.oauth_handlers.DeviceTokenManager")
    @patch("src.cloud.oauth_handlers._register_or_activate", new_callable=AsyncMock)
    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_valid_bootstrap_registers_device_and_issues_token(
        self, mock_handoff_cls, mock_register, mock_token_cls
    ):
        mock_handoff_cls.return_value.consume_handoff.return_value = {"purpose": "device_bootstrap", "user_id": "u1"}
        mock_register.return_value = {"id": "device-1", "device_name": "macbook"}
        mock_token_cls.return_value.issue_token.return_value = "bst_device_abc123"

        request = _mock_request(body={"code": "valid-bootstrap-code", "device": self._DEVICE_BODY})
        result = asyncio.run(oauth_handlers.device_bootstrap_redeem(request))

        self.assertEqual(result.status_code, 201)
        import json
        payload = json.loads(result.body)
        self.assertEqual(payload["device_token"], "bst_device_abc123")
        self.assertEqual(payload["device"]["id"], "device-1")
        mock_register.assert_called_once()
        self.assertEqual(mock_register.call_args.args[0], "u1")  # user_id from handoff, not the request body
        mock_token_cls.return_value.issue_token.assert_called_once_with("u1", "device-1", unittest.mock.ANY)

    @patch("src.cloud.oauth_handlers.HandoffManager")
    def test_second_redemption_of_bootstrap_code_fails(self, mock_handoff_cls):
        mock_handoff_cls.return_value.consume_handoff.side_effect = [
            {"purpose": "device_bootstrap", "user_id": "u1"}, None,
        ]
        request = _mock_request(body={"code": "one-time-bootstrap", "device": self._DEVICE_BODY})
        with patch("src.cloud.oauth_handlers._register_or_activate", new_callable=AsyncMock) as mock_register, \
             patch("src.cloud.oauth_handlers.DeviceTokenManager") as mock_token_cls:
            mock_register.return_value = {"id": "device-1", "device_name": "macbook"}
            mock_token_cls.return_value.issue_token.return_value = "bst_device_abc123"
            first = asyncio.run(oauth_handlers.device_bootstrap_redeem(request))
            second = asyncio.run(oauth_handlers.device_bootstrap_redeem(request))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 401)


if __name__ == "__main__":
    unittest.main()
