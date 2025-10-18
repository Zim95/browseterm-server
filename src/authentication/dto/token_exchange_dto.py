from pydantic import BaseModel
from typing import Optional


class TokenExchangeRequestModel(BaseModel):
    '''
    Token exchange request model
    '''
    code: str
    state: str
    provider: str


class TokenExchangeResponseModel(BaseModel):
    '''
    Token exchange response model from OAuth provider
    '''
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
