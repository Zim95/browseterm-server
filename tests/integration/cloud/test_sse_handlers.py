'''
GET /events/stream (P10) - public but possession-gated by an sse_token query param, same "mock
the boundary" convention as test_auth_api.py: patch RedisSessionManager where sse_handlers.py
imports it, never touch real Redis/Postgres.

Only the pre-stream auth/validation branches are exercised here (they return a plain JSONResponse
immediately). The success path's StreamingResponse wraps an async generator that blocks on
request.is_disconnected()/queue.get() - deliberately NOT iterated in a unit test (it would hang
waiting on a queue nothing ever fills); we only assert it's the right response type/media_type.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request
from fastapi.responses import StreamingResponse

from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel
import src.cloud.sse_handlers as sse_handlers


def _mock_request(query_params: dict) -> MagicMock:
    request = MagicMock(spec=Request)
    request.query_params = query_params
    return request


class TestEventsStream(unittest.TestCase):
    def test_missing_token_rejected(self):
        request = _mock_request({})
        result = asyncio.run(sse_handlers.events_stream(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.sse_handlers.RedisSessionManager")
    def test_invalid_or_expired_token_rejected(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager.validate_sse_token.return_value = None
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "bogus"})
        result = asyncio.run(sse_handlers.events_stream(request))
        self.assertEqual(result.status_code, 401)
        mock_manager.validate_sse_token.assert_called_once_with("bogus")

    @patch("src.cloud.sse_handlers.RedisSessionManager")
    def test_token_valid_but_session_expired_rejected(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager.validate_sse_token.return_value = "session-1"
        mock_manager.validate_session.return_value = SessionValidationModel(is_valid=False, session_data=None)
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "sse-token-1"})
        result = asyncio.run(sse_handlers.events_stream(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.sse_handlers.RedisSessionManager")
    def test_session_with_no_user_id_rejected(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager.validate_sse_token.return_value = "session-1"
        mock_manager.validate_session.return_value = SessionValidationModel(
            is_valid=True,
            session_data=SessionDataModel(user_info={}, subscription_info={}, current_subscription_plan={}),
        )
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "sse-token-1"})
        result = asyncio.run(sse_handlers.events_stream(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.sse_handlers.RedisSessionManager")
    def test_valid_token_and_session_returns_stream(self, mock_manager_cls):
        '''Never trust a client-supplied user_id - there isn't one in this request at all; the
        stream subscribes using the user_id resolved from the validated session only.'''
        mock_manager = MagicMock()
        mock_manager.validate_sse_token.return_value = "session-1"
        mock_manager.validate_session.return_value = SessionValidationModel(
            is_valid=True,
            session_data=SessionDataModel(user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}),
        )
        mock_manager_cls.return_value = mock_manager
        request = _mock_request({"token": "sse-token-1"})
        result = asyncio.run(sse_handlers.events_stream(request))
        self.assertIsInstance(result, StreamingResponse)
        self.assertEqual(result.media_type, "text/event-stream")


if __name__ == "__main__":
    unittest.main()
