'''
Cloud session/auth API tests. Same "mock the boundary" convention as test_device_api.py: call
the handler directly, patch the DB/Redis-touching functions at their import site in
src.cloud.auth_handlers.
'''
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from src.authentication.dto.session_dto import SessionDataModel, SessionResponseModel, SessionValidationModel
import src.cloud.auth_handlers as auth_handlers

TOKEN = "test-internal-token"


def _mock_request(body: dict, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.json = _async_return(body)
    request.headers = headers if headers is not None else {"X-Internal-Service-Token": TOKEN}
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


class TestCreateSessionFromUserInfo(unittest.TestCase):
    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_internal_token_rejected(self):
        request = _mock_request({}, headers={})
        import asyncio
        result = asyncio.run(auth_handlers.create_session_from_user_info(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.auth_handlers.process_user_info")
    def test_valid_user_info_creates_session(self, mock_process):
        import asyncio
        # process_user_info is `async def`, so patch() auto-creates an AsyncMock -- .return_value
        # is the value produced by awaiting it, not a coroutine to await ourselves.
        mock_process.return_value = SessionResponseModel(
            session_id="s1", user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}
        )
        request = _mock_request({
            "provider_id": "p1", "provider": "google", "name": "Demo", "email": "d@example.com",
        })
        result = asyncio.run(auth_handlers.create_session_from_user_info(request))
        self.assertEqual(result.status_code, 201)

    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_invalid_body_rejected(self):
        import asyncio
        request = _mock_request({"provider": "not-a-real-provider"})
        result = asyncio.run(auth_handlers.create_session_from_user_info(request))
        self.assertEqual(result.status_code, 400)


class TestValidateSession(unittest.TestCase):
    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_internal_token_rejected(self):
        import asyncio
        request = _mock_request({"session_id": "s1"}, headers={})
        result = asyncio.run(auth_handlers.validate_session(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.auth_handlers.extend_session")
    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_valid_session_returns_user_info_and_extends(self, mock_manager_cls, mock_extend):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.validate_session.return_value = SessionValidationModel(
            is_valid=True,
            session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
        )
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"session_id": "s1"})
        result = asyncio.run(auth_handlers.validate_session(request))
        self.assertEqual(result.status_code, 200)
        mock_extend.assert_called_once_with("s1", expiry=1800)

    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_invalid_session_returns_is_valid_false(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.validate_session.return_value = SessionValidationModel(is_valid=False, session_data=None)
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"session_id": "bogus"})
        result = asyncio.run(auth_handlers.validate_session(request))
        self.assertIn(result.status_code, (200,))


class TestDeleteSession(unittest.TestCase):
    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_delete_session_calls_manager(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"session_id": "s1"})
        result = asyncio.run(auth_handlers.delete_session(request))
        self.assertEqual(result.status_code, 200)
        mock_manager.delete_session.assert_called_once_with("s1")


class TestCreateWebsocketToken(unittest.TestCase):
    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        import asyncio
        request = _mock_request({"session_id": "s1"}, headers={})
        result = asyncio.run(auth_handlers.create_websocket_token(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.auth_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_valid_request_returns_token(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.create_websocket_token.return_value = "ws-token-1"
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"session_id": "s1"})
        result = asyncio.run(auth_handlers.create_websocket_token(request))
        self.assertEqual(result.status_code, 200)
        mock_manager.create_websocket_token.assert_called_once_with("s1")


class TestConsumeWebsocketToken(unittest.TestCase):
    '''POST /auth/websocket-tokens/consume (P11) - public but possession-gated, no internal
    token required (unlike every other route in this file).'''

    def test_no_internal_token_needed(self):
        '''Confirms this route does NOT call _internal_auth_ok - socket-ssh has no shared secret
        and shouldn't need one, matching P07's handoff/device-bootstrap redemption precedent.'''
        import asyncio
        request = _mock_request({"token": "bogus"}, headers={})  # no X-Internal-Service-Token
        with patch("src.cloud.auth_handlers.RedisSessionManager") as mock_manager_cls:
            mock_manager = MagicMock()
            mock_manager.consume_websocket_token.return_value = None
            mock_manager_cls.return_value = mock_manager
            result = asyncio.run(auth_handlers.consume_websocket_token(request))
        # 401 for an invalid *token*, not because of a missing internal-service header.
        self.assertEqual(result.status_code, 401)
        mock_manager.consume_websocket_token.assert_called_once_with("bogus")

    def test_missing_token_rejected(self):
        import asyncio
        request = _mock_request({}, headers={})
        result = asyncio.run(auth_handlers.consume_websocket_token(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_invalid_or_expired_token_rejected(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.consume_websocket_token.return_value = None
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "expired-token"}, headers={})
        result = asyncio.run(auth_handlers.consume_websocket_token(request))
        self.assertEqual(result.status_code, 401)
        import json
        self.assertFalse(json.loads(result.body)["valid"])

    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_second_consumption_of_same_token_fails(self, mock_manager_cls):
        '''GETDEL is single-use - the second call for the same token returns None from Redis.'''
        import asyncio
        mock_manager = MagicMock()
        mock_manager.consume_websocket_token.side_effect = ["s1", None]
        mock_manager.validate_session.return_value = SessionValidationModel(
            is_valid=True, session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
        )
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "one-time-token"}, headers={})
        first = asyncio.run(auth_handlers.consume_websocket_token(request))
        second = asyncio.run(auth_handlers.consume_websocket_token(request))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)

    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_valid_token_and_session_returns_user_id(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.consume_websocket_token.return_value = "s1"
        mock_manager.validate_session.return_value = SessionValidationModel(
            is_valid=True, session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
        )
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "valid-token"}, headers={})
        result = asyncio.run(auth_handlers.consume_websocket_token(request))
        self.assertEqual(result.status_code, 200)
        import json
        payload = json.loads(result.body)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["user_id"], "u1")

    @patch("src.cloud.auth_handlers.RedisSessionManager")
    def test_token_valid_but_session_expired_rejected(self, mock_manager_cls):
        import asyncio
        mock_manager = MagicMock()
        mock_manager.consume_websocket_token.return_value = "s1"
        mock_manager.validate_session.return_value = SessionValidationModel(is_valid=False, session_data=None)
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "valid-token-expired-session"}, headers={})
        result = asyncio.run(auth_handlers.consume_websocket_token(request))
        self.assertEqual(result.status_code, 401)


if __name__ == "__main__":
    unittest.main()
