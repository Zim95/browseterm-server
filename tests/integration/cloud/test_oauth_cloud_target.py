'''
Migration Part 3 - the new target=cloud browser-login path added to
src/cloud/oauth_handlers.py:oauth_start/oauth_callback. Separate file from the existing
test_oauth_handlers.py (left untouched) so the pre-existing target="local" test coverage for that
file stays exactly as it was - these tests are additive, not a replacement.
'''
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi import Request

import src.cloud.oauth_handlers as oauth_handlers
from src.authentication.dto.session_dto import SessionResponseModel


def _mock_request(query_params: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.query_params = query_params or {}
    request.path_params = {}
    request.headers = headers or {}
    return request


class TestOAuthStartCloudTarget(unittest.TestCase):
    @patch("src.cloud.oauth_handlers.OAuthStateManager")
    def test_target_cloud_is_accepted(self, mock_state_cls):
        mock_state_cls.return_value.create_state.return_value = "state-1"
        request = _mock_request(query_params={"target": "cloud"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_start(request))
        self.assertEqual(result.status_code, 302)
        mock_state_cls.return_value.create_state.assert_called_once_with("google", "cloud")


class TestOAuthCallbackCloudTarget(unittest.TestCase):
    @patch("src.cloud.oauth_handlers.set_session_cookies")
    @patch("src.cloud.oauth_handlers.process_user_info", new_callable=AsyncMock)
    @patch("src.cloud.oauth_handlers.PROVIDER_SERVICES")
    @patch("src.cloud.oauth_handlers.OAuthStateManager")
    def test_target_cloud_sets_cookie_directly_and_redirects_to_terminals(
        self, mock_state_cls, mock_provider_services, mock_process_user_info, mock_set_cookies
    ):
        mock_state_cls.return_value.consume_state.return_value = {"provider": "google", "target": "cloud"}
        mock_service_instance = MagicMock()
        mock_service_instance.fetch_user_info = AsyncMock(return_value=MagicMock())
        mock_provider_services.__contains__.return_value = True
        mock_provider_services.__getitem__.return_value = lambda: mock_service_instance
        mock_process_user_info.return_value = SessionResponseModel(
            session_id="s1", user_info={"id": "u1"}, subscription_info={}, current_subscription_plan={}
        )

        request = _mock_request(query_params={"code": "provider-code", "state": "valid-state"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))

        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.headers["location"], "/terminals")
        # No handoff code minted for this path - set_session_cookies (direct, same-origin) is
        # used instead, never a redirect carrying a code as a query param.
        self.assertNotIn("code=", result.headers["location"])
        mock_set_cookies.assert_called_once()
        self.assertEqual(mock_set_cookies.call_args.args[1], "s1")

    def test_early_failure_redirects_to_clouds_own_relative_login(self):
        '''Migration Part 3: an error before `target` is even known now goes to Cloud's own
        relative /login (the browser is always physically on Cloud's origin at this point),
        not Local's absolute callback URL.'''
        request = _mock_request(query_params={"error": "access_denied"})
        request.path_params = {"provider": "google"}
        result = asyncio.run(oauth_handlers.oauth_callback(request))
        self.assertEqual(result.status_code, 302)
        location = result.headers["location"]
        self.assertTrue(location.startswith("/login?"))
        self.assertIn("auth_result=error", location)


if __name__ == "__main__":
    unittest.main()
