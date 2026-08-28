# builtins
import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

# fastapi
from fastapi import Request

# module under test (imports cleanly off-cluster, same as test_resume_container.py)
import src.api_handlers as api_handlers

# data models
from src.data_models.payments import PaymentResponseData


def _mock_authenticated_request(body: dict, user_id: str) -> MagicMock:
    '''
    A FastAPI Request stand-in with .json() returning `body` and request.state.user_info set the
    way @authenticate_session actually sets it: a plain dict (see authentication_helpers.py /
    template_handlers.py's `request.state.user_info['id']`), NOT an object with a .id attribute.
    Regression coverage for the 'dict' object has no attribute 'id' bug (api_handlers.py used
    request.state.user_info.id instead of ['id']).
    '''
    request: MagicMock = MagicMock(spec=Request)
    request.json = AsyncMock(return_value=body)
    request.state.user_info = {'id': user_id, 'name': 'Test User', 'email': 'test@example.com'}
    return request


class TestCreatePaymentHandler(TestCase):
    '''
    Handler-level tests for api_handlers.create_payment.

    Calls the UNDECORATED handler via .__wrapped__ (same pattern as test_resume_container.py) so
    no Redis session is needed, and patches PaymentService at its import site in src.api_handlers
    so no live gRPC/payment-gateway is touched.
    '''

    def test_create_payment_extracts_user_id_from_dict_user_info(self) -> None:
        with patch('src.api_handlers.PaymentService') as mock_payment_service_cls:
            mock_service = MagicMock()
            mock_service.make_payment = AsyncMock(return_value=PaymentResponseData(
                payment_id='pay_test_001', status='SUCCESS', message='Payment request accepted'
            ))
            mock_payment_service_cls.return_value = mock_service

            request = _mock_authenticated_request(
                {'plan_id': 'developer', 'idempotency_key': 'idem-1'}, user_id='user-42'
            )
            response = asyncio.run(api_handlers.create_payment.__wrapped__(request=request))

            self.assertEqual(response.status_code, 200)
            mock_service.make_payment.assert_called_once_with(
                user_id='user-42',
                plan_id='developer',
                amount_minor=49900,
                currency='INR',
                idempotency_key='idem-1',
            )
