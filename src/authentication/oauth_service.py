'''
OAuth Token Exchange Service.
Handles token exchange and user info fetching for Google and GitHub.

To understand the implementation, read the following articles:
- Github Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-github-api-818383862591
- Google Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-google-apis-dead94d6866d

This handler handles: /<provider>-token-exchange
'''

# builtins
from abc import abstractmethod
from typing import Optional

# local
from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_AUTH_REDIRECT_URI, GOOGLE_ACCESS_TOKEN_URL, GOOGLE_USER_INFO_URL,
    GOOGLE_TOKEN_EXCHANGE_HEADERS,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_AUTH_REDIRECT_URI, GITHUB_ACCESS_TOKEN_URL, GITHUB_USER_INFO_URL,
    GITHUB_TOKEN_EXCHANGE_HEADERS
)

# modules
import httpx

# dtos
from src.authentication.dto.oauth_credentials_dto import OAuthCredentialsModel
from src.authentication.dto.token_exchange_dto import TokenExchangeResponseModel
from src.authentication.dto.user_info_dto import UserInfoModel

# transformers
from src.authentication.data_transformers.token_exchange_transformer import TokenExchangeTransformer
from src.authentication.data_transformers.google_user_info_transformer import GoogleUserInfoTransformer
from src.authentication.data_transformers.github_user_info_transformer import GithubUserInfoTransformer


class OAuthTokenExchangeService:

    def __init__(self, credentials: OAuthCredentialsModel) -> None:
        '''
        Initialize the OAuth token exchange service.
        '''
        self.credentials: OAuthCredentialsModel = credentials

    async def exchange_token(self, code: str) -> Optional[TokenExchangeResponseModel]:
        '''
        Exchange token for provider.
        Returns TokenExchangeResponseModel or None on failure
        '''
        token_data: dict = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
            'redirect_uri': self.credentials.redirect_uri
        }
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                self.credentials.access_token_url, 
                data=token_data, 
                headers=self.credentials.token_exchange_headers
            )
            if response.status_code != 200:
                print(f"Token exchange failed: {response.status_code}")
                return None
            token_result: dict = response.json()
            access_token: str = token_result.get('access_token')
            if not access_token:
                print("No access token received")
                return None
            # Transform to DTO
            return TokenExchangeTransformer.transform(token_result)


class OAuthUserInfoService:

    @abstractmethod
    async def get_credentials(self, code: str) -> Optional[OAuthCredentialsModel]:
        '''
        Get OAuth credentials for provider. To be implemented by the subclass.
        '''
        raise NotImplementedError("Please implement get_credentials!")

    @abstractmethod
    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        '''
        Transform user info from provider to UserInfoModel. To be implemented by the subclass.
        '''
        raise NotImplementedError("Please implement transform_user_info!")

    async def fetch_user_info(self, code: str) -> Optional[UserInfoModel]:
        '''
        1. Get the user info from the provider.
        2. Transform to standardized UserInfoModel
        Returns None if credentials or token exchange fails, raises exception for other errors
        '''
        try:
            credentials: Optional[OAuthCredentialsModel] = await self.get_credentials(code)
            if not credentials:
                print("Credentials not found for provider.")
                return None
            # Exchange token
            token_service: OAuthTokenExchangeService = OAuthTokenExchangeService(credentials)
            token_info: Optional[TokenExchangeResponseModel] = await token_service.exchange_token(code)
            if not token_info:
                print("Token info not found for provider.")
                return None
            # Fetch user info from provider API
            async with httpx.AsyncClient() as client:
                user_response: httpx.Response = await client.get(
                    credentials.user_info_url, 
                    headers={'Authorization': f'Bearer {token_info.access_token}'}
                )
                if user_response.status_code != 200:
                    print(f"Failed to fetch user info: {user_response.status_code}")
                    return None
                # Transform to UserInfoModel
                return self.transform_user_info(user_response.json())
        except NotImplementedError as ni:
            raise NotImplementedError(ni)
        except Exception as e:
            print(f"Error fetching user info: {e}")
            raise Exception(e)


class GoogleUserInfoService(OAuthUserInfoService):
    async def get_credentials(self, code: str) -> Optional[OAuthCredentialsModel]:
        return OAuthCredentialsModel(
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=GOOGLE_AUTH_REDIRECT_URI,
            access_token_url=GOOGLE_ACCESS_TOKEN_URL,
            user_info_url=GOOGLE_USER_INFO_URL,
            token_exchange_headers=GOOGLE_TOKEN_EXCHANGE_HEADERS
        )

    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        return GoogleUserInfoTransformer.transform(user_info)


class GithubUserInfoService(OAuthUserInfoService):
    async def get_credentials(self, code: str) -> Optional[OAuthCredentialsModel]:
        return OAuthCredentialsModel(
            client_id=GITHUB_CLIENT_ID,
            client_secret=GITHUB_CLIENT_SECRET,
            redirect_uri=GITHUB_AUTH_REDIRECT_URI,
            access_token_url=GITHUB_ACCESS_TOKEN_URL,
            user_info_url=GITHUB_USER_INFO_URL,
            token_exchange_headers=GITHUB_TOKEN_EXCHANGE_HEADERS
        )

    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        return GithubUserInfoTransformer.transform(user_info)
