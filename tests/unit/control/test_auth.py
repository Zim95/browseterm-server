'''
Part 6 required tests: "valid/revoked/wrong-device authentication."
'''
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from browseterm_db.models.devices import DeviceStatus
from browseterm_db.operations import OperationResult

from src.control.auth import authenticate_stream


def _fake_context(auth_header: str = None) -> MagicMock:
    context = MagicMock()
    metadata = [("authorization", auth_header)] if auth_header else []
    context.invocation_metadata = MagicMock(return_value=metadata)
    return context


class TestAuthenticateStream(IsolatedAsyncioTestCase):

    @patch("src.control.auth.DeviceOps")
    @patch("src.control.auth.DeviceTokenManager")
    async def test_valid_token_and_active_device_succeeds(self, mock_token_manager_cls, mock_device_ops_cls) -> None:
        mock_token_manager_cls.return_value.validate_token.return_value = {
            "user_id": "user-1", "device_id": "device-1", "scopes": ["device:control"],
        }
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "device-1", "user_id": "user-1", "status": DeviceStatus.ACTIVE.value, "revoked_at": None},
        )
        auth = await authenticate_stream(_fake_context("Bearer bst_device_validtoken"))
        self.assertIsNotNone(auth)
        self.assertEqual(auth.device_id, "device-1")
        self.assertEqual(auth.user_id, "user-1")

    async def test_missing_authorization_header_fails(self) -> None:
        auth = await authenticate_stream(_fake_context(None))
        self.assertIsNone(auth)

    async def test_non_bearer_authorization_header_fails(self) -> None:
        auth = await authenticate_stream(_fake_context("Basic somevalue"))
        self.assertIsNone(auth)

    @patch("src.control.auth.DeviceTokenManager")
    async def test_invalid_token_fails(self, mock_token_manager_cls) -> None:
        mock_token_manager_cls.return_value.validate_token.return_value = None
        auth = await authenticate_stream(_fake_context("Bearer bst_device_garbage"))
        self.assertIsNone(auth)

    @patch("src.control.auth.DeviceOps")
    @patch("src.control.auth.DeviceTokenManager")
    async def test_revoked_device_fails_even_with_a_valid_token(self, mock_token_manager_cls, mock_device_ops_cls) -> None:
        '''"Revoked token fails authentication" - the token itself may still validate (e.g. its
        Redis TTL hasn't expired yet), but the device row's revocation must still win.'''
        mock_token_manager_cls.return_value.validate_token.return_value = {
            "user_id": "user-1", "device_id": "device-1", "scopes": [],
        }
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "device-1", "user_id": "user-1", "status": DeviceStatus.REVOKED.value, "revoked_at": "2026-09-01T00:00:00Z"},
        )
        auth = await authenticate_stream(_fake_context("Bearer bst_device_validtoken"))
        self.assertIsNone(auth)

    @patch("src.control.auth.DeviceOps")
    @patch("src.control.auth.DeviceTokenManager")
    async def test_device_row_not_found_fails(self, mock_token_manager_cls, mock_device_ops_cls) -> None:
        '''Covers "wrong-device" in the sense of a token whose device/user pair no longer
        resolves to a real row (e.g. deleted) - find_one is always scoped to BOTH device_id and
        user_id together, so a token for one user's device can never authenticate as another
        user's device even if the IDs happened to collide.'''
        mock_token_manager_cls.return_value.validate_token.return_value = {
            "user_id": "user-1", "device_id": "device-of-another-user", "scopes": [],
        }
        mock_device_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        auth = await authenticate_stream(_fake_context("Bearer bst_device_validtoken"))
        self.assertIsNone(auth)
        mock_device_ops_cls.return_value.find_one.assert_called_once_with(
            {"id": "device-of-another-user", "user_id": "user-1"}
        )
