'''
Migration Part 3 - Cloud's own direct browser session authentication. Same "mock the boundary"
convention as the rest of this test suite: patch RedisSessionManager at its import site in
src.cloud.session_auth, never a real Redis connection.
'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

import src.cloud.session_auth as session_auth
from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel


def _mock_request(cookies: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    request.headers = headers or {}
    request.state = MagicMock()
    return request


def _session_data(**overrides) -> SessionDataModel:
    data = {"user_info": {"id": "u1", "name": "Ada", "email": "ada@example.com"}, "subscription_info": {}, "current_subscription_plan": {}}
    data.update(overrides)
    return SessionDataModel(**data)


class TestGetSessionData(unittest.TestCase):
    def test_missing_cookie_returns_none(self):
        request = _mock_request(cookies={})
        result = asyncio.run(session_auth.get_session_data(request))
        self.assertIsNone(result)

    @patch("src.cloud.session_auth.RedisSessionManager")
    def test_invalid_session_returns_none(self, mock_manager_cls):
        mock_manager_cls.return_value.validate_session.return_value = SessionValidationModel(is_valid=False, session_data=None, ttl=-2)
        request = _mock_request(cookies={"session": "bad-session-id"})
        result = asyncio.run(session_auth.get_session_data(request))
        self.assertIsNone(result)

    @patch("src.cloud.session_auth.RedisSessionManager")
    def test_valid_session_returns_data_and_extends_ttl(self, mock_manager_cls):
        session_data = _session_data()
        mock_manager_cls.return_value.validate_session.return_value = SessionValidationModel(is_valid=True, session_data=session_data, ttl=1000)
        request = _mock_request(cookies={"session": "good-session-id"})
        result = asyncio.run(session_auth.get_session_data(request))
        self.assertEqual(result.user_info["id"], "u1")
        mock_manager_cls.return_value.extend_session.assert_called_once_with("good-session-id", expiry=1800)


class TestCsrfOk(unittest.TestCase):
    def test_missing_header_fails(self):
        request = _mock_request(cookies={"csrf_token": "abc"}, headers={})
        self.assertFalse(session_auth.csrf_ok(request))

    def test_missing_cookie_fails(self):
        request = _mock_request(cookies={}, headers={"X-CSRF-Token": "abc"})
        self.assertFalse(session_auth.csrf_ok(request))

    def test_mismatched_values_fail(self):
        request = _mock_request(cookies={"csrf_token": "abc"}, headers={"X-CSRF-Token": "xyz"})
        self.assertFalse(session_auth.csrf_ok(request))

    def test_matching_values_pass(self):
        request = _mock_request(cookies={"csrf_token": "abc"}, headers={"X-CSRF-Token": "abc"})
        self.assertTrue(session_auth.csrf_ok(request))


class TestCookieHelpers(unittest.TestCase):
    def test_set_session_cookies_sets_both_httponly_and_csrf(self):
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={})
        session_auth.set_session_cookies(response, "session-id-1")
        set_cookie_headers = response.headers.getlist("set-cookie")
        self.assertEqual(len(set_cookie_headers), 2)
        session_header = next(h for h in set_cookie_headers if h.startswith("session="))
        csrf_header = next(h for h in set_cookie_headers if h.startswith("csrf_token="))
        self.assertIn("HttpOnly", session_header)
        self.assertNotIn("HttpOnly", csrf_header)
        self.assertIn("session-id-1", session_header)

    def test_clear_session_cookies_zeroes_max_age(self):
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={})
        session_auth.clear_session_cookies(response)
        set_cookie_headers = response.headers.getlist("set-cookie")
        for header in set_cookie_headers:
            self.assertIn("Max-Age=0", header)


class TestRequirePageSession(unittest.TestCase):
    @patch("src.cloud.session_auth.RedisSessionManager")
    def test_missing_session_redirects_to_login(self, mock_manager_cls):
        mock_manager_cls.return_value.validate_session.return_value = SessionValidationModel(is_valid=False, session_data=None, ttl=-2)

        @session_auth.require_page_session
        async def handler(request):
            return "should not reach here"

        request = _mock_request(cookies={})
        result = asyncio.run(handler(request))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")

    @patch("src.cloud.session_auth.RedisSessionManager")
    def test_valid_session_populates_request_state_and_calls_handler(self, mock_manager_cls):
        session_data = _session_data()
        mock_manager_cls.return_value.validate_session.return_value = SessionValidationModel(is_valid=True, session_data=session_data, ttl=1000)

        @session_auth.require_page_session
        async def handler(request):
            return request.state.user_info["id"]

        request = _mock_request(cookies={"session": "good-session-id"})
        result = asyncio.run(handler(request))
        self.assertEqual(result, "u1")


if __name__ == "__main__":
    unittest.main()
