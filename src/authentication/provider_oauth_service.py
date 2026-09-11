'''
P07 - Cloud-owned Google/GitHub OAuth token exchange + user-info fetch.

Moved here from browseterm-server-local/src/authentication/oauth_service.py verbatim in
structure (same class shapes, same transform pipeline) - only the credentials source changed:
these classes now read GOOGLE_CLIENT_ID/SECRET/GITHUB_CLIENT_ID/SECRET from Cloud's own
src.common.config, and the redirect_uri they present to the provider is Cloud's own
/auth/<provider>/callback (src.common.config.GOOGLE_AUTH_REDIRECT_URI /
GITHUB_AUTH_REDIRECT_URI), never a Local or Desktop URL - see p07.md section 5. Local no longer
has any copy of this code (p07.md section 38/39 - provider secrets must not exist client-side).

Also holds `GoogleDeviceAuthService` (below), the OAuth Device Authorization Grant (RFC 8628)
counterpart used by Desktop's login flow so it never needs Local reachable to authenticate a
user - see the device-auth follow-up to p07.md. Same "Desktop never holds a provider secret"
principle applies: this class's GOOGLE_DEVICE_CLIENT_ID/SECRET never leave Cloud.
'''
from abc import abstractmethod
from typing import Optional

import httpx

from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_AUTH_REDIRECT_URI, GOOGLE_ACCESS_TOKEN_URL, GOOGLE_USER_INFO_URL,
    GOOGLE_TOKEN_EXCHANGE_HEADERS,
    GOOGLE_DEVICE_CLIENT_ID, GOOGLE_DEVICE_CLIENT_SECRET, GOOGLE_DEVICE_AUTHORIZATION_URL, GOOGLE_DEVICE_SCOPE,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_AUTH_REDIRECT_URI, GITHUB_ACCESS_TOKEN_URL, GITHUB_USER_INFO_URL,
    GITHUB_TOKEN_EXCHANGE_HEADERS, GITHUB_DEVICE_AUTHORIZATION_URL, GITHUB_AUTH_SCOPE,
)
from src.common.logging_setup import get_logger

from src.authentication.dto.oauth_credentials_dto import OAuthCredentialsModel
from src.authentication.dto.token_exchange_dto import TokenExchangeResponseModel
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.data_transformers.token_exchange_transformer import TokenExchangeTransformer
from src.authentication.data_transformers.google_user_info_transformer import GoogleUserInfoTransformer
from src.authentication.data_transformers.github_user_info_transformer import GithubUserInfoTransformer

logger = get_logger("provider_oauth_service")


class OAuthTokenExchangeService:
    def __init__(self, credentials: OAuthCredentialsModel) -> None:
        self.credentials: OAuthCredentialsModel = credentials

    async def exchange_token(self, code: str) -> Optional[TokenExchangeResponseModel]:
        token_data: dict = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
            'redirect_uri': self.credentials.redirect_uri,
        }
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                self.credentials.access_token_url, data=token_data, headers=self.credentials.token_exchange_headers
            )
            if response.status_code != 200:
                # Never log the provider code/token - only the outcome. See p07.md section 40.
                logger.warning("token exchange failed", extra={"status_code": response.status_code})
                return None
            token_result: dict = response.json()
            if not token_result.get('access_token'):
                logger.warning("no access token received")
                return None
            return TokenExchangeTransformer.transform(token_result)


class OAuthUserInfoService:
    @abstractmethod
    def get_credentials(self) -> OAuthCredentialsModel:
        raise NotImplementedError("Please implement get_credentials!")

    @abstractmethod
    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        raise NotImplementedError("Please implement transform_user_info!")

    async def fetch_user_info(self, code: str) -> Optional[UserInfoModel]:
        '''Returns None on any failure (bad code, provider error) - the caller (oauth_handlers.py)
        redirects the browser back to Local's login with an error, it never raises through to a
        500 for a routine "user cancelled/denied" case.'''
        credentials = self.get_credentials()
        token_service = OAuthTokenExchangeService(credentials)
        token_info = await token_service.exchange_token(code)
        if not token_info:
            return None
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                credentials.user_info_url, headers={'Authorization': f'Bearer {token_info.access_token}'}
            )
            if user_response.status_code != 200:
                logger.warning("user info API error", extra={"status_code": user_response.status_code})
                return None
            return self.transform_user_info(user_response.json())


class GoogleUserInfoService(OAuthUserInfoService):
    def get_credentials(self) -> OAuthCredentialsModel:
        return OAuthCredentialsModel(
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=GOOGLE_AUTH_REDIRECT_URI,
            access_token_url=GOOGLE_ACCESS_TOKEN_URL,
            user_info_url=GOOGLE_USER_INFO_URL,
            token_exchange_headers=GOOGLE_TOKEN_EXCHANGE_HEADERS,
        )

    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        return GoogleUserInfoTransformer.transform(user_info)


class GithubUserInfoService(OAuthUserInfoService):
    def get_credentials(self) -> OAuthCredentialsModel:
        return OAuthCredentialsModel(
            client_id=GITHUB_CLIENT_ID,
            client_secret=GITHUB_CLIENT_SECRET,
            redirect_uri=GITHUB_AUTH_REDIRECT_URI,
            access_token_url=GITHUB_ACCESS_TOKEN_URL,
            user_info_url=GITHUB_USER_INFO_URL,
            token_exchange_headers=GITHUB_TOKEN_EXCHANGE_HEADERS,
        )

    def transform_user_info(self, user_info: dict) -> UserInfoModel:
        return GithubUserInfoTransformer.transform(user_info)


PROVIDER_SERVICES = {"google": GoogleUserInfoService, "github": GithubUserInfoService}
PROVIDER_AUTH_META_URLS = {
    "google": "https://accounts.google.com/o/oauth2/auth",
    "github": "https://github.com/login/oauth/authorize",
}
PROVIDER_SCOPES = {"google": "openid email profile", "github": "user:email user"}
PROVIDER_CLIENT_IDS = {"google": GOOGLE_CLIENT_ID, "github": GITHUB_CLIENT_ID}
PROVIDER_REDIRECT_URIS = {"google": GOOGLE_AUTH_REDIRECT_URI, "github": GITHUB_AUTH_REDIRECT_URI}


class GoogleDeviceAuthService:
    '''OAuth Device Authorization Grant (RFC 8628) against Google -- the login path Desktop uses
    so it never needs Local reachable to authenticate (see the device-auth follow-up to p07.md).
    Uses the separate GOOGLE_DEVICE_CLIENT_ID/SECRET ("TVs and Limited Input devices" client type;
    device flow is not available on the "Web application" client GoogleUserInfoService above uses).
    Desktop never holds this secret -- it only calls Cloud's /auth/device/start and
    /auth/device/poll (src/cloud/oauth_handlers.py), which are the only callers of this class.

    See GithubDeviceAuthService below for the GitHub counterpart - both providers are wired up in
    DEVICE_FLOW_SERVICES, though GitHub's will error until its OAuth App has "Enable Device Flow"
    turned on (a manual console step, tracked separately).
    '''

    async def start(self) -> Optional[dict]:
        '''POST to Google's device authorization endpoint. Returns Google's raw response dict
        (device_code, user_code, verification_url, expires_in, interval) on success, None on any
        failure -- same "never raise for a routine failure" convention as fetch_user_info above.'''
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_DEVICE_AUTHORIZATION_URL,
                data={"client_id": GOOGLE_DEVICE_CLIENT_ID, "scope": GOOGLE_DEVICE_SCOPE},
                headers=GOOGLE_TOKEN_EXCHANGE_HEADERS,
            )
            if response.status_code != 200:
                logger.warning("device authorization start failed", extra={"status_code": response.status_code})
                return None
            return response.json()

    async def poll(self, device_code: str) -> dict:
        '''POST to Google's token endpoint using the device_code grant. Always returns Google's
        raw JSON response, success or not -- per RFC 8628, a pending/denied/expired poll is a
        normal (non-200) response with an "error" field, not a transport failure; the caller
        (src.cloud.oauth_handlers.device_auth_poll) is the one that interprets that field.'''
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_ACCESS_TOKEN_URL,
                data={
                    "client_id": GOOGLE_DEVICE_CLIENT_ID,
                    "client_secret": GOOGLE_DEVICE_CLIENT_SECRET,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers=GOOGLE_TOKEN_EXCHANGE_HEADERS,
            )
            return response.json()

    async def fetch_user_info(self, access_token: str) -> Optional[UserInfoModel]:
        '''Same userinfo call/transform GoogleUserInfoService uses, just handed an access token
        obtained via the device grant instead of the authorization-code grant.'''
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                GOOGLE_USER_INFO_URL, headers={'Authorization': f'Bearer {access_token}'}
            )
            if user_response.status_code != 200:
                logger.warning("device flow user info API error", extra={"status_code": user_response.status_code})
                return None
            return GoogleUserInfoTransformer.transform(user_response.json())


class GithubDeviceAuthService:
    '''OAuth Device Authorization Grant against GitHub - the same RFC 8628 shape as
    GoogleDeviceAuthService, but reuses the existing GITHUB_CLIENT_ID/SECRET (the authorization-
    code flow's own OAuth App): GitHub's device flow is a per-app toggle ("Enable Device Flow"),
    not a separate client type the way Google's is. Its token endpoint also doesn't take a client
    secret at all (client_id + device_code is enough) - one genuine simplification over Google's
    flow, not an oversight here.

    Wired up in full so the desktop login UI can offer a GitHub button alongside Google's, but
    this will fail until the GitHub OAuth App this project's GITHUB_CLIENT_ID belongs to has
    "Enable Device Flow" turned on in its own settings (a manual console step, tracked separately
    - see the two-button login follow-up to the device-auth work above). Until then, `start()`
    gets a real error response from GitHub (e.g. a "device flow not enabled" error) rather than a
    device_code, which device_auth_start already turns into a clean 502 for the caller.'''

    async def start(self) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_DEVICE_AUTHORIZATION_URL,
                data={"client_id": GITHUB_CLIENT_ID, "scope": GITHUB_AUTH_SCOPE},
                headers=GITHUB_TOKEN_EXCHANGE_HEADERS,
            )
            body = response.json()
            if response.status_code != 200 or not body.get("device_code"):
                logger.warning(
                    "github device authorization start failed",
                    extra={"status_code": response.status_code, "error": body.get("error")},
                )
                return None
            return body

    async def poll(self, device_code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_ACCESS_TOKEN_URL,
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers=GITHUB_TOKEN_EXCHANGE_HEADERS,
            )
            return response.json()

    async def fetch_user_info(self, access_token: str) -> Optional[UserInfoModel]:
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                GITHUB_USER_INFO_URL, headers={'Authorization': f'Bearer {access_token}'}
            )
            if user_response.status_code != 200:
                logger.warning("device flow user info API error", extra={"status_code": user_response.status_code})
                return None
            return GithubUserInfoTransformer.transform(user_response.json())


DEVICE_FLOW_SERVICES = {"google": GoogleDeviceAuthService, "github": GithubDeviceAuthService}
