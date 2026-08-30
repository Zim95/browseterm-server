'''Cloud subscription-resolution API tests.'''
import asyncio
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Request

from browseterm_db.operations import OperationResult
import src.cloud.subscription_handlers as subscription_handlers

TOKEN = "test-internal-token"


def _mock_request(query_params: dict = None, headers: dict = None) -> MagicMock:
    request = MagicMock(spec=Request)
    request.query_params = query_params or {}
    request.headers = headers if headers is not None else {"X-Internal-Service-Token": TOKEN}
    return request


class TestGetCurrentSubscription(unittest.TestCase):
    @patch("src.cloud.subscription_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_token_rejected(self):
        request = _mock_request({"user_id": "u1"}, headers={})
        result = asyncio.run(subscription_handlers.get_current_subscription(request))
        self.assertEqual(result.status_code, 401)

    @patch("src.cloud.subscription_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    def test_missing_user_id_rejected(self):
        request = _mock_request({})
        result = asyncio.run(subscription_handlers.get_current_subscription(request))
        self.assertEqual(result.status_code, 400)

    @patch("src.cloud.subscription_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.subscription_handlers.SubscriptionTypeOps")
    @patch("src.cloud.subscription_handlers.SubscriptionOps")
    def test_existing_subscription_returns_its_type(self, mock_sub_ops_cls, mock_type_ops_cls):
        mock_sub_ops = MagicMock()
        mock_sub_ops.find_one.return_value = OperationResult(
            success=True, data={"id": "sub1", "subscription_type_id": "type1"}
        )
        mock_sub_ops_cls.return_value = mock_sub_ops
        mock_type_ops = MagicMock()
        mock_type_ops.find_one.return_value = OperationResult(success=True, data={"id": "type1", "type": "pro"})
        mock_type_ops_cls.return_value = mock_type_ops

        request = _mock_request({"user_id": "u1"})
        result = asyncio.run(subscription_handlers.get_current_subscription(request))
        self.assertEqual(result.status_code, 200)
        mock_sub_ops.insert.assert_not_called()

    @patch("src.cloud.subscription_handlers.CLOUD_INTERNAL_API_TOKEN", TOKEN)
    @patch("src.cloud.subscription_handlers.SubscriptionTypeOps")
    @patch("src.cloud.subscription_handlers.SubscriptionOps")
    def test_no_subscription_creates_free_one(self, mock_sub_ops_cls, mock_type_ops_cls):
        mock_sub_ops = MagicMock()
        mock_sub_ops.find_one.return_value = OperationResult(success=True, data=None)
        mock_sub_ops.insert.return_value = OperationResult(
            success=True, data={"id": "sub1", "subscription_type_id": "free1"}
        )
        mock_sub_ops_cls.return_value = mock_sub_ops
        mock_type_ops = MagicMock()
        mock_type_ops.find.return_value = OperationResult(
            success=True, data=[{"id": "free1", "type": "free", "duration_days": 30}]
        )
        mock_type_ops.find_one.return_value = OperationResult(
            success=True, data={"id": "free1", "type": "free", "duration_days": 30}
        )
        mock_type_ops_cls.return_value = mock_type_ops

        request = _mock_request({"user_id": "u1"})
        result = asyncio.run(subscription_handlers.get_current_subscription(request))
        self.assertEqual(result.status_code, 200)
        mock_sub_ops.insert.assert_called_once()
        self.assertEqual(mock_sub_ops.insert.call_args.args[0]["user_id"], "u1")


if __name__ == "__main__":
    unittest.main()
