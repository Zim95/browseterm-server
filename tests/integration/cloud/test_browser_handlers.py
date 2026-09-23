'''
Migration Part 3 - Cloud's browser-facing container/lifecycle JSON API
(src/cloud/browser_handlers.py). The whole point of this module is the trust-boundary fix: never
let a browser reach the internal-token-gated container_handlers.py routes directly, and never
trust a body/query-supplied user_id even when a real session is present. These tests exist
specifically to prove that boundary holds - every route here is tested for (a) 401 with no/invalid
session, (b) 403 on a state-changing route with a missing/wrong CSRF header, and (c) that a
container owned by a DIFFERENT user is never returned/mutated (IDOR), before ever asserting the
happy path.
'''
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult

import src.cloud.browser_handlers as browser_handlers

USER_A = "user-a"
USER_B = "user-b"
CONTAINER_A = "container-a-id"


def _mock_request(cookies: dict = None, headers: dict = None, body: dict = None, path_params: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.cookies = cookies if cookies is not None else {"session": "sess-1", "csrf_token": "csrf-1"}
    request.headers = headers if headers is not None else {"X-CSRF-Token": "csrf-1"}
    request.path_params = path_params or {}
    request.json = _async_return(body or {})
    request.state = MagicMock()
    return request


def _async_return(value):
    async def _coro():
        return value
    return _coro


def _container_row(user_id=USER_A, **overrides) -> dict:
    row = {"id": CONTAINER_A, "user_id": user_id, "name": "my-workspace", "status": "Running", "device_id": "device-1", "placement_generation": 1}
    row.update(overrides)
    return row


def _patch_session_ok(user_id=USER_A):
    '''Patches get_json_session to simulate an authenticated session for `user_id`, matching
    how session_auth.py actually populates request.state - real cookie/Redis mechanics are
    already covered by test_session_auth.py, no need to re-mock Redis here too.'''
    async def _fake(request):
        from src.authentication.dto.session_dto import SessionDataModel
        session_data = SessionDataModel(user_info={"id": user_id}, subscription_info={}, current_subscription_plan={})
        request.state.user_info = session_data.user_info
        return session_data
    return patch("src.cloud.browser_handlers.get_json_session", side_effect=_fake)


def _patch_session_none():
    return patch("src.cloud.browser_handlers.get_json_session", new_callable=AsyncMock, return_value=None)


class TestAuthRequired(unittest.TestCase):
    '''Every route 401s with no valid session - before anything else is even checked.'''

    def test_list_containers_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.list_containers(_mock_request()))
        self.assertEqual(result.status_code, 401)

    def test_get_container_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.get_container(_mock_request(path_params={"container_id": CONTAINER_A})))
        self.assertEqual(result.status_code, 401)

    def test_create_container_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.create_container(_mock_request()))
        self.assertEqual(result.status_code, 401)

    def test_delete_container_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.delete_container(_mock_request(path_params={"container_id": CONTAINER_A})))
        self.assertEqual(result.status_code, 401)

    def test_hibernate_container_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.hibernate_container(_mock_request(path_params={"container_id": CONTAINER_A})))
        self.assertEqual(result.status_code, 401)

    def test_save_container_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.save_container(_mock_request(path_params={"container_id": CONTAINER_A})))
        self.assertEqual(result.status_code, 401)

    def test_device_quota_requires_session(self):
        with _patch_session_none():
            result = asyncio.run(browser_handlers.device_quota(_mock_request()))
        self.assertEqual(result.status_code, 401)

    def test_logout_does_not_require_session(self):
        '''Logout with no session is a harmless no-op (nothing to revoke), not a 401 - matches
        browseterm-server-local's own logout, which never gated on an authenticated session
        either (you should always be able to clear cookies).'''
        with patch("src.cloud.browser_handlers.RedisSessionManager"):
            result = asyncio.run(browser_handlers.logout(_mock_request(cookies={"csrf_token": "csrf-1"})))
        self.assertEqual(result.status_code, 200)


class TestCsrfRequired(unittest.TestCase):
    '''State-changing routes 403 on a missing/mismatched CSRF header, even with a fully valid
    session - this is what actually stops a cross-site forged request riding the ambient cookie.'''

    def test_create_container_without_csrf_header_rejected(self):
        request = _mock_request(cookies={"session": "sess-1", "csrf_token": "csrf-1"}, headers={})
        with _patch_session_ok():
            result = asyncio.run(browser_handlers.create_container(request))
        self.assertEqual(result.status_code, 403)

    def test_delete_container_without_csrf_header_rejected(self):
        request = _mock_request(cookies={"session": "sess-1", "csrf_token": "csrf-1"}, headers={}, path_params={"container_id": CONTAINER_A})
        with _patch_session_ok():
            result = asyncio.run(browser_handlers.delete_container(request))
        self.assertEqual(result.status_code, 403)

    def test_resume_container_wrong_csrf_header_rejected(self):
        request = _mock_request(
            cookies={"session": "sess-1", "csrf_token": "csrf-1"},
            headers={"X-CSRF-Token": "wrong-value"},
            path_params={"container_id": CONTAINER_A},
        )
        with _patch_session_ok():
            result = asyncio.run(browser_handlers.resume_container(request))
        self.assertEqual(result.status_code, 403)

    def test_hibernate_container_without_csrf_header_rejected(self):
        request = _mock_request(cookies={"session": "sess-1", "csrf_token": "csrf-1"}, headers={}, path_params={"container_id": CONTAINER_A})
        with _patch_session_ok():
            result = asyncio.run(browser_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 403)

    def test_save_container_without_csrf_header_rejected(self):
        request = _mock_request(cookies={"session": "sess-1", "csrf_token": "csrf-1"}, headers={}, path_params={"container_id": CONTAINER_A})
        with _patch_session_ok():
            result = asyncio.run(browser_handlers.save_container(request))
        self.assertEqual(result.status_code, 403)

    def test_logout_without_csrf_header_rejected(self):
        request = _mock_request(cookies={"session": "sess-1", "csrf_token": "csrf-1"}, headers={})
        result = asyncio.run(browser_handlers.logout(request))
        self.assertEqual(result.status_code, 403)


class TestOwnershipIDOR(unittest.TestCase):
    '''A container owned by a different user is never visible or mutable through this session,
    no matter what path/body values are supplied.'''

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_get_container_owned_by_another_user_returns_404(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_B):
            result = asyncio.run(browser_handlers.get_container(request))
        self.assertEqual(result.status_code, 404)
        # Proves the lookup itself was scoped to the CALLER's own user_id, not container_id alone.
        mock_ops_cls.return_value.find_one.assert_called_once_with({"id": CONTAINER_A, "user_id": USER_B})

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_delete_container_owned_by_another_user_returns_404_not_deleted(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_B):
            result = asyncio.run(browser_handlers.delete_container(request))
        self.assertEqual(result.status_code, 404)
        mock_ops_cls.return_value.delete.assert_not_called()

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_hibernate_container_owned_by_another_user_returns_404(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_B):
            result = asyncio.run(browser_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 404)

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_save_container_owned_by_another_user_returns_404(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None, error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_B):
            result = asyncio.run(browser_handlers.save_container(request))
        self.assertEqual(result.status_code, 404)

    def test_create_container_never_trusts_body_supplied_user_id(self):
        '''Even if the browser-supplied body carries a (forged) user_id for someone else, the
        container is created for the SESSION's own user - never the body's.'''
        forged_body = {
            "user_id": USER_B, "name": "x", "cpu_limit": "1", "memory_limit": "1Gi", "storage_limit": "2Gi",
        }
        request = _mock_request(body=forged_body)
        captured = {}

        async def _capture_internal_create(shim):
            captured["body"] = await shim.json()
            from fastapi.responses import JSONResponse
            return JSONResponse(content={"container": {}}, status_code=201)

        with _patch_session_ok(USER_A), \
                patch("src.cloud.browser_handlers._internal_create_container", side_effect=_capture_internal_create):
            asyncio.run(browser_handlers.create_container(request))

        self.assertEqual(captured["body"]["user_id"], USER_A)


class TestHappyPaths(unittest.TestCase):
    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_list_containers_returns_only_callers_own(self, mock_ops_cls):
        mock_ops_cls.return_value.find.return_value = OperationResult(success=True, data=[_container_row()], error=None)
        request = _mock_request()
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.list_containers(request))
        self.assertEqual(result.status_code, 200)
        mock_ops_cls.return_value.find.assert_called_once_with({"user_id": USER_A}, exclude_deleted=True)

    @patch("src.cloud.browser_handlers._hibernate_container_via_device_command", new_callable=AsyncMock)
    @patch("src.cloud.browser_handlers.ContainerOps")
    @patch("src.cloud.browser_handlers.DEVICE_COMMAND_HIBERNATE_ENABLED", True)
    def test_hibernate_running_container_with_device_succeeds(self, mock_ops_cls, mock_hibernate):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"), error=None)
        from fastapi.responses import JSONResponse
        mock_hibernate.return_value = JSONResponse(content={"command": {}}, status_code=202)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 202)
        mock_hibernate.assert_called_once()

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_hibernate_non_running_container_rejected(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Hibernated"), error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.hibernate_container(request))
        self.assertEqual(result.status_code, 409)

    @patch("src.cloud.browser_handlers._save_container_via_device_command", new_callable=AsyncMock)
    @patch("src.cloud.browser_handlers.ContainerOps")
    @patch("src.cloud.browser_handlers.DEVICE_COMMAND_SAVE_ENABLED", True)
    def test_save_running_container_with_device_succeeds(self, mock_ops_cls, mock_save):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"), error=None)
        from fastapi.responses import JSONResponse
        mock_save.return_value = JSONResponse(content={"command": {}}, status_code=202)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.save_container(request))
        self.assertEqual(result.status_code, 202)
        mock_save.assert_called_once()

    @patch("src.cloud.browser_handlers.ContainerOps")
    def test_save_non_running_container_rejected(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Hibernated"), error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.save_container(request))
        self.assertEqual(result.status_code, 409)

    @patch("src.cloud.browser_handlers.ContainerOps")
    @patch("src.cloud.browser_handlers.DEVICE_COMMAND_SAVE_ENABLED", False)
    def test_save_rejected_when_flag_disabled(self, mock_ops_cls):
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=_container_row(status="Running"), error=None)
        request = _mock_request(path_params={"container_id": CONTAINER_A})
        with _patch_session_ok(USER_A):
            result = asyncio.run(browser_handlers.save_container(request))
        self.assertEqual(result.status_code, 503)


if __name__ == "__main__":
    unittest.main()
