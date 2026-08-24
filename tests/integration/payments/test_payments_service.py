# builtins
import asyncio
from unittest import TestCase
from unittest.mock import MagicMock

import grpc

# grpc types
from payment_gateway_spec.payment_types_pb2 import PaymentResponse as GRPCPaymentResponse
from payment_gateway_spec.payment_types_pb2 import PaymentStatus

# module under test
from src.payments.payments_service import PaymentService

# exceptions
from src.common.exceptions import PaymentGatewayException, PaymentGatewayUnavailableException


class _FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode, details: str) -> None:
        self._code = code
        self._details = details

    def code(self) -> grpc.StatusCode:
        return self._code

    def details(self) -> str:
        return self._details


class TestPaymentService(TestCase):
    '''
    Unit tests for PaymentService.make_payment.

    We bypass PaymentService.__init__ (which reads certs from Kubernetes secrets and opens a
    gRPC channel) and inject a mocked stub, mirroring
    tests/integration/containers/test_save_container_service.py. No live cluster or gRPC
    server is contacted.
    '''
    def setUp(self) -> None:
        self.payment_service: PaymentService = PaymentService.__new__(PaymentService)
        self.mock_stub: MagicMock = MagicMock()
        self.payment_service.stub = self.mock_stub

    def test_make_payment_returns_hardcoded_success(self) -> None:
        self.mock_stub.makePayment.return_value = GRPCPaymentResponse(
            payment_id="pay_test_001",
            status=PaymentStatus.PAYMENT_STATUS_SUCCESS,
            message="Payment request accepted",
        )

        result = asyncio.run(
            self.payment_service.make_payment(
                user_id="user-1", plan_id="developer", amount_minor=49900, currency="INR"
            )
        )

        # stub called exactly once
        self.mock_stub.makePayment.assert_called_once()

        # the request handed to the stub carries the correct values
        called_request = self.mock_stub.makePayment.call_args.args[0]
        self.assertEqual(called_request.user_id, "user-1")
        self.assertEqual(called_request.plan_id, "developer")
        self.assertEqual(called_request.amount_minor, 49900)
        self.assertEqual(called_request.currency, "INR")

        # x-request-id metadata is forwarded
        called_kwargs = self.mock_stub.makePayment.call_args.kwargs
        metadata_keys = dict(called_kwargs["metadata"])
        self.assertIn("x-request-id", metadata_keys)
        self.assertIn("timeout", called_kwargs)

        self.assertEqual(result.payment_id, "pay_test_001")
        self.assertEqual(result.status, "SUCCESS")

    def test_make_payment_raises_unavailable_on_rpc_unavailable(self) -> None:
        self.mock_stub.makePayment.side_effect = _FakeRpcError(
            grpc.StatusCode.UNAVAILABLE, "connection refused"
        )

        with self.assertRaises(PaymentGatewayUnavailableException):
            asyncio.run(
                self.payment_service.make_payment(
                    user_id="user-1", plan_id="developer", amount_minor=49900, currency="INR"
                )
            )

    def test_make_payment_wraps_other_rpc_errors(self) -> None:
        self.mock_stub.makePayment.side_effect = _FakeRpcError(
            grpc.StatusCode.INTERNAL, "boom"
        )

        with self.assertRaises(PaymentGatewayException):
            asyncio.run(
                self.payment_service.make_payment(
                    user_id="user-1", plan_id="developer", amount_minor=49900, currency="INR"
                )
            )
