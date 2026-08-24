'''
End to end tests send actual api input and compare the response with the expected response.
'''

from unittest import TestCase
from unittest.mock import patch
from fastapi import Response
from fastapi.testclient import TestClient
from app import app


class TestPaymentEndpoint(TestCase):
    '''
    End to end test for the /create-payment endpoint.
    '''
    def setUp(self) -> None:
        '''
        Setup the API test client.
        '''
        self.client: TestClient = TestClient(app, follow_redirects=False)

    def test_create_payment_unauthenticated_is_rejected_without_calling_payment_gateway(self) -> None:
        '''
        An unauthenticated request must be redirected to /login by @authenticate_session,
        and payment-gateway must never be contacted.
        '''
        with patch("src.payments.payments_service.PaymentService") as mock_payment_service_cls:
            response: Response = self.client.post("/create-payment", json={"plan_id": "developer"})

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["location"], "/login")
            mock_payment_service_cls.assert_not_called()
