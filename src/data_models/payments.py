from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    '''
    Create payment request data.

    plan_id is the only value the browser is trusted to supply for v0. amount_minor/currency
    are resolved server-side (hardcoded for now — see payments_service.py TODO) rather than
    trusted from the request body, since PAYMENTS.md explicitly calls out not treating
    browser-provided amounts as authoritative.
    '''
    plan_id: str = "developer"


class PaymentResponseData(BaseModel):
    '''
    Payment response data returned to the frontend.
    '''
    payment_id: str
    status: str
    message: str
