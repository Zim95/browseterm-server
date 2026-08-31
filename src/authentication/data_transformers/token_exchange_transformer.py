from typing import Dict, Any
from src.authentication.data_transformers import InputDataTransformer
from src.authentication.dto.token_exchange_dto import TokenExchangeResponseModel


class TokenExchangeTransformer(InputDataTransformer):
    '''
    Transform OAuth token exchange response to TokenExchangeResponseModel
    '''
    @classmethod
    def transform(cls, input_data: Dict[str, Any]) -> TokenExchangeResponseModel:
        return TokenExchangeResponseModel(
            access_token=input_data.get('access_token', ''),
            refresh_token=input_data.get('refresh_token'),
            expires_in=input_data.get('expires_in')
        )
