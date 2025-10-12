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
import asyncio
from typing import Dict, Any, Optional

from src.db_ops.subscription_db_ops import get_or_create_free_subscription

# local
from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_AUTH_REDIRECT_URI, GOOGLE_ACCESS_TOKEN_URL, GOOGLE_USER_INFO_URL,
    GOOGLE_TOKEN_EXCHANGE_HEADERS,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_AUTH_REDIRECT_URI, GITHUB_ACCESS_TOKEN_URL, GITHUB_USER_INFO_URL,
    GITHUB_TOKEN_EXCHANGE_HEADERS
)

# modules
import httpx
from browseterm_db.models.users import AuthProvider


class OAuthTokenExchangeService:

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, access_token_url: str, token_exchange_headers: dict) -> None:
        '''
        Initialize the OAuth token exchange service.
        '''
        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.redirect_uri: str = redirect_uri
        self.access_token_url: str = access_token_url
        self.token_exchange_headers: dict = token_exchange_headers

    async def exchange_token(self, code: str) -> Optional[Dict[str, Any]]:
        '''
        Exchange token for provider.
        '''
        token_data: dict = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(self.access_token_url, data=token_data, headers=self.token_exchange_headers)
            if response.status_code != 200:
                print(f"Token exchange failed: {response.status_code}")
                return None
            token_result: dict = response.json()
            access_token: str = token_result.get('access_token')
            if not access_token:
                print("No access token received")
                return None
            return {
                'access_token': access_token,
                'refresh_token': token_result.get('refresh_token'),
                'expires_in': token_result.get('expires_in')
            }


class OAuthUserInfoService:

    @abstractmethod
    async def get_credentials(self, code: str) -> Optional[Dict[str, Any]]:
        '''
        Exchange token for provider. To be implemented by the subclass.
        '''
        raise NotImplementedError("Please implement get_credentials!")

    @abstractmethod
    def format_user_info(self, user_info: dict) -> dict:
        '''
        Format user info from provider. To be implemented by the subclass.
        '''
        raise NotImplementedError("Please implement get_user_info!")

    @abstractmethod
    async def fetch_user_info(self, code: str) -> dict:
        '''
        1. Get the user info from the provider.
        2. Get the subscription info from the database.
        '''
        try:
            credentials: Optional[Dict[str, Any]] = await self.get_credentials(code)
            if not credentials:
                raise ValueError("Credentials not found for provider.")
            token_info: Optional[Dict[str, Any]] = await OAuthTokenExchangeService(
                client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                redirect_uri=credentials['redirect_uri'],
                access_token_url=credentials['access_token_url'],
                token_exchange_headers=credentials['token_exchange_headers']
            ).exchange_token(code)
            if not token_info:
                raise ValueError("Token info not found for provider.")
            access_token: str = token_info.get('access_token')
            if not access_token:
                raise ValueError("Access token not found for provider.")
            async with httpx.AsyncClient() as client:
                user_response: httpx.Response = await client.get(
                    credentials['user_info_url'], headers={'Authorization': f'Bearer {access_token}'})
                return self.format_user_info(user_response.json())
        except NotImplementedError as ni:
            raise NotImplementedError(ni)
        except Exception as e:
            print(f"Error fetching user info: {e}")
            raise Exception(e)


class GoogleUserInfoService(OAuthUserInfoService):
    async def get_credentials(self, code: str) -> Optional[Dict[str, Any]]:
        return {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_AUTH_REDIRECT_URI,
            'access_token_url': GOOGLE_ACCESS_TOKEN_URL,
            'user_info_url': GOOGLE_USER_INFO_URL,
            'token_exchange_headers': GOOGLE_TOKEN_EXCHANGE_HEADERS
        }

    def format_user_info(self, user_info: dict) -> dict:
        return {
            'provider_id': user_info.get('id'),
            'name': user_info.get('name'),
            'email': user_info.get('email'),
            'profile_picture_url': user_info.get('picture'),
            'provider': AuthProvider.GOOGLE
        }


class GithubUserInfoService(OAuthUserInfoService):
    async def get_credentials(self, code: str) -> Optional[Dict[str, Any]]:
        return {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'redirect_uri': GITHUB_AUTH_REDIRECT_URI,
            'access_token_url': GITHUB_ACCESS_TOKEN_URL,
            'user_info_url': GITHUB_USER_INFO_URL,
            'token_exchange_headers': GITHUB_TOKEN_EXCHANGE_HEADERS
        }

    def format_user_info(self, user_info: dict) -> dict:
        return {
            'provider_id': str(user_info.get('id')),
            'name': user_info.get('name'),
            'email': user_info.get('email'),
            'profile_picture_url': user_info.get('avatar_url'),
            'provider': AuthProvider.GITHUB
        }
