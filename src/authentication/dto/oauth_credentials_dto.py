from pydantic import BaseModel


class OAuthCredentialsModel(BaseModel):
    '''
    OAuth credentials model
    '''
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token_url: str
    user_info_url: str
    token_exchange_headers: dict
