from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    '''
    Create payment request data.

    plan_id and idempotency_key are the only values the browser is trusted to supply for v0.
    amount_minor/currency are resolved server-side (hardcoded for now — see payments_service.py
    TODO) rather than trusted from the request body, since PAYMENTS.md explicitly calls out not
    treating browser-provided amounts as authoritative. idempotency_key carries no pricing/trust
    weight — it's a client-generated dedup token (one per checkout attempt, reused across
    retries), safe to accept as-is; it's only logged today, not yet enforced server-side.
    '''
    plan_id: str = "developer"
    idempotency_key: str


class PaymentResponseData(BaseModel):
    '''
    Payment response data returned to the frontend.
    '''
    payment_id: str
    status: str
    message: str
