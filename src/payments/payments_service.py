# modules
import asyncio

from payment_gateway_spec.payment_service_pb2_grpc import PaymentGatewayAPIStub
from payment_gateway_spec.payment_types_pb2 import PaymentRequest as GRPCPaymentRequest
from payment_gateway_spec.payment_types_pb2 import PaymentResponse as GRPCPaymentResponse
from payment_gateway_spec.payment_types_pb2 import PaymentStatus

# utils
from src.common.exceptions import PaymentGatewayException, PaymentGatewayUnavailableException
from src.common.k8s_secrets import read_cert_from_k8s_secret

# config
from src.common.config import PAYMENT_GATEWAY_CERTS_SECRET_NAME, PAYMENT_GATEWAY_HOST, PAYMENT_GATEWAY_PORT, NAMESPACE

# grpc utils
from src.common.grpc_utils import GRPCUtils

# logging
from src.common.logging_setup import get_logger, request_id_var

logger = get_logger("payments_service")

# third party
import grpc

# data models
from src.data_models.payments import PaymentResponseData

# gRPC call deadline. PAYMENTS.md explicitly requires that a payment-gateway outage returns a
# controlled error rather than hanging the request indefinitely; ContainerService's stub calls
# set no deadline today, so this is a deliberate addition rather than a copy of that pattern.
PAYMENT_CALL_TIMEOUT_SECONDS = 5

_STATUS_NAME = {
    PaymentStatus.PAYMENT_STATUS_UNSPECIFIED: "UNSPECIFIED",
    PaymentStatus.PAYMENT_STATUS_SUCCESS: "SUCCESS",
    PaymentStatus.PAYMENT_STATUS_FAILED: "FAILED",
}


class PaymentService:
    '''
    A service for the PaymentGateway API.
    '''
    def __init__(self) -> None:
        '''
        Initialize the PaymentService.
        '''
        # read certificates directly from Kubernetes secrets
        self.client_key: bytes = read_cert_from_k8s_secret(
            PAYMENT_GATEWAY_CERTS_SECRET_NAME,
            NAMESPACE,
            'client.key'
        )
        self.client_cert: bytes = read_cert_from_k8s_secret(
            PAYMENT_GATEWAY_CERTS_SECRET_NAME,
            NAMESPACE,
            'client.crt'
        )
        self.ca_cert: bytes = read_cert_from_k8s_secret(
            PAYMENT_GATEWAY_CERTS_SECRET_NAME,
            NAMESPACE,
            'ca.crt'
        )

        # create GRPC channel and stub
        self.grpc_utils: GRPCUtils = GRPCUtils(
            host=PAYMENT_GATEWAY_HOST,
            port=PAYMENT_GATEWAY_PORT,
            stub_class=PaymentGatewayAPIStub,
            secure=True,
            client_key=self.client_key,
            client_cert=self.client_cert,
            ca_cert=self.ca_cert
        )
        self.channel: grpc.Channel = self.grpc_utils.channel
        self.stub: PaymentGatewayAPIStub = self.grpc_utils.stub

    async def make_payment(self, user_id: str, plan_id: str, amount_minor: int, currency: str) -> PaymentResponseData:
        '''
        Call payment-gateway's makePayment RPC and translate the response/errors for the API layer.

        user_id is resolved server-side by the caller (from the authenticated session) — never
        accepted from the browser. amount_minor/currency are hardcoded by the caller for v0;
        # TODO: once real plans exist, resolve amount_minor/currency server-side from plan_id
        instead of accepting/hardcoding them here — never trust a browser-provided amount.
        '''
        try:
            request_id: str = request_id_var.get()
            grpc_request: GRPCPaymentRequest = GRPCPaymentRequest(
                user_id=user_id,
                plan_id=plan_id,
                amount_minor=amount_minor,
                currency=currency,
                request_id=request_id,
            )
            grpc_response: GRPCPaymentResponse = await asyncio.to_thread(
                self.stub.makePayment,
                grpc_request,
                metadata=(("x-request-id", request_id),),
                timeout=PAYMENT_CALL_TIMEOUT_SECONDS,
            )
            return PaymentResponseData(
                payment_id=grpc_response.payment_id,
                status=_STATUS_NAME.get(grpc_response.status, "UNSPECIFIED"),
                message=grpc_response.message,
            )
        except grpc.RpcError as re:
            if re.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                logger.error(f"payment-gateway unavailable: {re.details()}")
                raise PaymentGatewayUnavailableException(re.details())
            logger.error(f"payment-gateway RPC error: {re.details()}")
            raise PaymentGatewayException(re.details())
