'''
Migration Part 3 - Cloud's browser page routes (src/cloud/page_handlers.py). Covers the doc's own
required tests for this part: unauthenticated access to protected routes redirects to /login,
and authenticated pages actually render (200) from Cloud directly.
'''
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult

import src.cloud.page_handlers as page_handlers

USER_A = "user-a"


def _mock_request(cookies: dict = None, path_params: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies or {}
    request.headers = {}
    request.path_params = path_params or {}
    request.state = MagicMock()
    request.url.path = "/"
    return request


def _patch_session_ok(user_id=USER_A):
    async def _fake(request):
        from src.authentication.dto.session_dto import SessionDataModel
        session_data = SessionDataModel(user_info={"id": user_id, "name": "Ada", "email": "ada@x.com"}, subscription_info={}, current_subscription_plan={})
        request.state.user_info = session_data.user_info
        request.state.subscription_info = {}
        request.state.current_subscription_plan = {}
        request.state.session_id = "sess-1"
        return session_data
    return patch("src.cloud.page_handlers.get_session_data", side_effect=_fake)


def _patch_session_none():
    return patch("src.cloud.page_handlers.get_session_data", new_callable=AsyncMock, return_value=None)


def _patch_decorator_session_ok(user_id=USER_A):
    '''@require_page_session (src/cloud/session_auth.py) calls get_session_data from ITS OWN
    module scope, not page_handlers' - routes using that decorator (terminals/profile/devices/
    terminal_page) need this patch target instead of _patch_session_ok above.'''
    async def _fake(request):
        from src.authentication.dto.session_dto import SessionDataModel
        return SessionDataModel(user_info={"id": user_id, "name": "Ada", "email": "ada@x.com"}, subscription_info={}, current_subscription_plan={})
    return patch("src.cloud.session_auth.get_session_data", side_effect=_fake)


def _patch_decorator_session_none():
    return patch("src.cloud.session_auth.get_session_data", new_callable=AsyncMock, return_value=None)


class TestUnauthenticatedRedirects(unittest.TestCase):
    '''Every protected page redirects (302) to /login with no valid session - the doc's own
    explicitly required test for this migration part.'''

    def test_index_redirects_to_login_when_unauthenticated(self):
        with _patch_session_none():
            result = asyncio.run(page_handlers.index(_mock_request()))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")

    def test_index_redirects_to_terminals_when_authenticated(self):
        with _patch_session_ok():
            result = asyncio.run(page_handlers.index(_mock_request(cookies={"session": "sess-1"})))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/terminals")

    def test_login_page_renders_for_unauthenticated_visitor(self):
        with _patch_session_none():
            result = asyncio.run(page_handlers.login(_mock_request()))
        self.assertEqual(result.status_code, 200)

    def test_login_page_redirects_away_when_already_authenticated(self):
        with _patch_session_ok():
            result = asyncio.run(page_handlers.login(_mock_request(cookies={"session": "sess-1"})))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/terminals")

    def test_terminals_redirects_to_login_when_unauthenticated(self):
        with _patch_decorator_session_none():
            result = asyncio.run(page_handlers.terminals(_mock_request()))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")

    def test_profile_redirects_to_login_when_unauthenticated(self):
        with _patch_decorator_session_none():
            result = asyncio.run(page_handlers.profile(_mock_request()))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")

    def test_devices_redirects_to_login_when_unauthenticated(self):
        with _patch_decorator_session_none():
            result = asyncio.run(page_handlers.devices(_mock_request()))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")

    def test_terminal_page_redirects_to_login_when_unauthenticated(self):
        with _patch_decorator_session_none():
            result = asyncio.run(page_handlers.terminal_page(_mock_request(path_params={"container_id": "c1"})))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/login")


class TestAuthenticatedRendering(unittest.TestCase):
    @patch("src.cloud.page_handlers.RedisSessionManager")
    @patch("src.cloud.page_handlers.DeviceOps")
    @patch("src.cloud.page_handlers.ImageOps")
    def test_terminals_page_renders_for_authenticated_user(self, mock_image_ops, mock_device_ops, mock_redis):
        mock_image_ops.return_value.find.return_value = OperationResult(success=True, data=[], error=None)
        mock_device_ops.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        mock_redis.return_value.create_sse_token.return_value = "sse-token-1"
        with _patch_decorator_session_ok():
            result = asyncio.run(page_handlers.terminals(_mock_request(cookies={"session": "sess-1"})))
        self.assertEqual(result.status_code, 200)

    @patch("src.cloud.page_handlers.DeviceOps")
    def test_devices_page_only_lists_callers_own_devices(self, mock_device_ops):
        mock_device_ops.return_value.find.return_value = OperationResult(success=True, data=[], error=None)
        with _patch_decorator_session_ok(USER_A):
            result = asyncio.run(page_handlers.devices(_mock_request(cookies={"session": "sess-1"})))
        self.assertEqual(result.status_code, 200)
        mock_device_ops.return_value.find.assert_called_once_with({"user_id": USER_A})

    @patch("src.cloud.page_handlers.RedisSessionManager")
    @patch("src.cloud.page_handlers.ContainerOps")
    def test_terminal_page_for_container_owned_by_another_user_shows_not_found(self, mock_container_ops, mock_redis):
        '''IDOR check: a container id belonging to someone else never renders their terminal
        info - the lookup itself is scoped to {id, user_id} together.'''
        mock_container_ops.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        mock_redis.return_value.create_sse_token.return_value = "sse-token-1"
        with _patch_decorator_session_ok("user-b"):
            result = asyncio.run(page_handlers.terminal_page(_mock_request(cookies={"session": "sess-1"}, path_params={"container_id": "someone-elses-container"})))
        self.assertEqual(result.status_code, 200)  # renders the page itself with an error message, not a raw 404
        mock_container_ops.return_value.find_one.assert_called_once_with({"id": "someone-elses-container", "user_id": "user-b"})


if __name__ == "__main__":
    unittest.main()
