from pydantic import BaseModel


# Pydantic models for OAuth token exchange
class TokenExchangeRequest(BaseModel):
    code: str
    state: str
    provider: str
