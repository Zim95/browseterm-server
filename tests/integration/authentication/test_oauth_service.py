# builtins
from unittest import TestCase
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import httpx

# local
from src.authentication.oauth_service import (
    OAuthTokenExchangeService,
    GoogleUserInfoService,
    GithubUserInfoService
)
from src.authentication.dto.oauth_credentials_dto import OAuthCredentialsModel
from src.authentication.dto.token_exchange_dto import TokenExchangeResponseModel
from src.authentication.dto.user_info_dto import UserInfoModel
from browseterm_db.models.users import AuthProvider


class TestOAuthTokenExchangeService(TestCase):
    '''
    Test OAuthTokenExchangeService with mocked HTTP calls.
    Tests both success and failure scenarios.
    '''

    def setUp(self) -> None:
        '''
        Setup test credentials and OAuth service.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client_id',
            client_secret='test_client_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.provider.com/token',
            user_info_url='https://api.provider.com/user',
            token_exchange_headers={'Accept': 'application/json'}
        )
        self.service: OAuthTokenExchangeService = OAuthTokenExchangeService(self.credentials)
        self.test_code: str = 'test_authorization_code'

    def tearDown(self) -> None:
        '''
        Close event loop.
        '''
        self.loop.close()

    @patch('httpx.AsyncClient')
    def test_exchange_token_success(self, mock_client_class) -> None:
        '''
        Test successful token exchange.
        '''
        # Mock successful response
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
            'expires_in': 3600
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: TokenExchangeResponseModel = self.loop.run_until_complete(
            self.service.exchange_token(self.test_code)
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.access_token, 'mock_access_token')
        self.assertEqual(result.refresh_token, 'mock_refresh_token')
        self.assertEqual(result.expires_in, 3600)

    @patch('httpx.AsyncClient')
    def test_exchange_token_failure_status_code(self, mock_client_class) -> None:
        '''
        Test token exchange with non-200 status code.
        '''
        # Mock failed response
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 400

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: TokenExchangeResponseModel | None = self.loop.run_until_complete(self.service.exchange_token(self.test_code))

        # Assert
        self.assertIsNone(result)

    @patch('httpx.AsyncClient')
    def test_exchange_token_no_access_token(self, mock_client_class) -> None:
        '''
        Test token exchange when response doesn't contain access_token.
        '''
        # Mock response without access_token
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': 'invalid_grant'
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: TokenExchangeResponseModel | None = self.loop.run_until_complete(self.service.exchange_token(self.test_code))

        # Assert
        self.assertIsNone(result)


class TestGoogleUserInfoService(TestCase):
    '''
    Test GoogleUserInfoService with mocked HTTP calls.
    Tests both success and failure scenarios for Google OAuth.
    '''

    def setUp(self) -> None:
        '''
        Setup Google OAuth service.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.service: GoogleUserInfoService = GoogleUserInfoService()
        self.test_code: str = 'google_auth_code'

    def tearDown(self) -> None:
        '''
        Close event loop.
        '''
        self.loop.close()

    @patch.object(GoogleUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_success(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test successful user info fetch from Google.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.google.com/token',
            user_info_url='https://www.googleapis.com/oauth2/v1/userinfo',
            token_exchange_headers={'Accept': 'application/json'}
        )

        # Mock token exchange response
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'google_access_token',
            'expires_in': 3600
        }

        # Mock user info response
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            'id': 'google123',
            'name': 'Google User',
            'email': 'user@gmail.com',
            'picture': 'https://example.com/pic.jpg'
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel = self.loop.run_until_complete(
            self.service.fetch_user_info(self.test_code)
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.provider_id, 'google123')
        self.assertEqual(result.name, 'Google User')
        self.assertEqual(result.email, 'user@gmail.com')
        self.assertEqual(result.provider, AuthProvider.GOOGLE)

    @patch.object(GoogleUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_token_exchange_failure(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test user info fetch when token exchange fails.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.google.com/token',
            user_info_url='https://www.googleapis.com/oauth2/v1/userinfo',
            token_exchange_headers={'Accept': 'application/json'}
        )
        mock_get_credentials.return_value = mock_credentials

        # Mock failed token exchange
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 400

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel | None = self.loop.run_until_complete(self.service.fetch_user_info(self.test_code))

        # Assert
        self.assertIsNone(result)

    @patch.object(GoogleUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_api_failure(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test user info fetch when Google API call fails.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.google.com/token',
            user_info_url='https://www.googleapis.com/oauth2/v1/userinfo',
            token_exchange_headers={'Accept': 'application/json'}
        )
        mock_get_credentials.return_value = mock_credentials

        # Mock successful token exchange
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'google_access_token'
        }

        # Mock failed user info response
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 401

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel | None = self.loop.run_until_complete(self.service.fetch_user_info(self.test_code))

        # Assert
        self.assertIsNone(result)


class TestGithubUserInfoService(TestCase):
    '''
    Test GithubUserInfoService with mocked HTTP calls.
    Tests both success and failure scenarios for GitHub OAuth.
    '''

    def setUp(self) -> None:
        '''
        Setup GitHub OAuth service.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.service: GithubUserInfoService = GithubUserInfoService()
        self.test_code: str = 'github_auth_code'

    def tearDown(self) -> None:
        '''
        Close event loop.
        '''
        self.loop.close()

    @patch.object(GithubUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_success(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test successful user info fetch from GitHub.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://github.com/login/oauth/access_token',
            user_info_url='https://api.github.com/user',
            token_exchange_headers={'Accept': 'application/json'}
        )

        # Mock token exchange response
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'github_access_token',
            'token_type': 'bearer'
        }

        # Mock user info response
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            'id': 12345,
            'name': 'GitHub User',
            'email': 'user@github.com',
            'avatar_url': 'https://avatars.githubusercontent.com/u/12345'
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel = self.loop.run_until_complete(
            self.service.fetch_user_info(self.test_code)
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.provider_id, '12345')
        self.assertEqual(result.name, 'GitHub User')
        self.assertEqual(result.email, 'user@github.com')
        self.assertEqual(result.provider, AuthProvider.GITHUB)

    @patch.object(GithubUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_token_exchange_failure(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test user info fetch when token exchange fails.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.google.com/token',
            user_info_url='https://www.googleapis.com/oauth2/v1/userinfo',
            token_exchange_headers={'Accept': 'application/json'}
        )
        mock_get_credentials.return_value = mock_credentials

        # Mock failed token exchange
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 401

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel | None = self.loop.run_until_complete(self.service.fetch_user_info(self.test_code))

        # Assert
        self.assertIsNone(result)

    @patch.object(GithubUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_with_minimal_data(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test user info fetch with minimal GitHub API response.
        '''
        # Mock get_credentials
        mock_credentials: OAuthCredentialsModel = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://github.com/login/oauth/access_token',
            user_info_url='https://api.github.com/user',
            token_exchange_headers={'Accept': 'application/json'}
        )
        mock_get_credentials.return_value = mock_credentials

        # Mock token exchange response
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'github_access_token'
        }

        # Mock minimal user info response
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            'id': 99999,
            'name': None,
            'email': None,
            'avatar_url': None
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel = self.loop.run_until_complete(
            self.service.fetch_user_info(self.test_code)
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.provider_id, '99999')
        self.assertIsNone(result.name)
        self.assertIsNone(result.email)
        self.assertEqual(result.provider, AuthProvider.GITHUB)
