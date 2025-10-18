# builtins
from unittest import TestCase
from typing import Dict, Any, Optional
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json

# local
from src.authentication.authentication_service import (
    GoogleAuthenticationService,
    GithubAuthenticationService
)
from src.authentication.oauth_service import GoogleUserInfoService, GithubUserInfoService
from src.authentication.dto.token_exchange_dto import TokenExchangeRequestModel
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.dto.session_dto import SessionResponseModel
from browseterm_db.models.users import AuthProvider
from fastapi import HTTPException
from fastapi.responses import Response


class TestGoogleAuthenticationService(TestCase):
    '''
    Test GoogleAuthenticationService with mocked dependencies.
    Tests both success and failure scenarios for Google authentication.
    '''

    def setUp(self) -> None:
        '''
        Setup test data and service.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.service: GoogleAuthenticationService = GoogleAuthenticationService()
        self.request: TokenExchangeRequestModel = TokenExchangeRequestModel(
            code='google_auth_code',
            state='random_state',
            provider='google'
        )

        self.user_info: UserInfoModel = UserInfoModel(
            provider_id='google123',
            name='Google User',
            email='user@gmail.com',
            profile_picture_url='https://example.com/pic.jpg',
            provider=AuthProvider.GOOGLE
        )

    def tearDown(self) -> None:
        """
        Close event loop.
        """
        self.loop.close()

    @patch('src.authentication.authentication_service.process_user_info')
    @patch.object(GoogleAuthenticationService, 'fetch_user_info')
    def test_login_success(self, mock_fetch_user_info, mock_process_user_info) -> None:
        '''
        Test successful Google login flow.
        '''
        # Mock fetch_user_info
        mock_fetch_user_info.return_value = self.user_info

        # Mock process_user_info
        mock_session_response: SessionResponseModel = SessionResponseModel(
            session_id='test-session-123',
            user_info={'id': 1, 'name': 'Google User'},
            subscription_info={'id': 10, 'status': 'active'},
            current_subscription_plan={'id': 1, 'name': 'Free'}
        )
        mock_process_user_info.return_value = mock_session_response

        # Execute
        response: Response = self.loop.run_until_complete(self.service.login(self.request))

        # Assert
        self.assertEqual(response.status_code, 200)

        # Check that session cookie was set
        cookies: str = response.headers.get('set-cookie', '')
        self.assertIn('session=', cookies)

        # Check response body
        body: Dict[str, Any] = json.loads(response.body)
        self.assertEqual(body['session_id'], 'test-session-123')

    @patch.object(GoogleAuthenticationService, 'fetch_user_info')
    def test_login_failure_no_user_info(self, mock_fetch_user_info) -> None:
        '''
        Test login failure when user info cannot be fetched.
        '''
        # Mock fetch_user_info returning None
        mock_fetch_user_info.return_value = None

        # Execute and assert exception
        with self.assertRaises(HTTPException) as context:
            self.loop.run_until_complete(self.service.login(self.request))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn('Failed to fetch user information', context.exception.detail)

    @patch('src.authentication.authentication_service.process_user_info')
    @patch.object(GoogleAuthenticationService, 'fetch_user_info')
    def test_login_failure_session_creation(self, mock_fetch_user_info, mock_process_user_info) -> None:
        '''
        Test login failure when session creation fails.
        '''
        # Mock fetch_user_info
        mock_fetch_user_info.return_value = self.user_info

        # Mock process_user_info with no session_id
        mock_session_response: SessionResponseModel = SessionResponseModel(
            session_id='',  # Empty session ID
            user_info={},
            subscription_info={},
            current_subscription_plan={}
        )
        mock_process_user_info.return_value = mock_session_response

        # Execute and assert exception
        with self.assertRaises(HTTPException) as context:
            self.loop.run_until_complete(self.service.login(self.request))

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn('Failed to create session', context.exception.detail)

    @patch.object(GoogleUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_success(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test successful user info fetch for Google.
        '''
        # Mock get_credentials
        from src.authentication.dto.oauth_credentials_dto import OAuthCredentialsModel
        mock_get_credentials.return_value = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://oauth.google.com/token',
            user_info_url='https://www.googleapis.com/oauth2/v1/userinfo',
            token_exchange_headers={'Accept': 'application/json'}
        )

        # Mock token exchange
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'google_token'
        }

        # Mock user info API
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            'id': 'google123',
            'name': 'Test User',
            'email': 'test@gmail.com',
            'picture': 'https://example.com/pic.jpg'
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel = self.loop.run_until_complete(self.service.fetch_user_info('test_code'))

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.provider, AuthProvider.GOOGLE)


class TestGithubAuthenticationService(TestCase):
    '''
    Test GithubAuthenticationService with mocked dependencies.
    Tests both success and failure scenarios for GitHub authentication.
    '''

    def setUp(self) -> None:
        '''
        Setup test data and service.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.service: GithubAuthenticationService = GithubAuthenticationService()
        self.request: TokenExchangeRequestModel = TokenExchangeRequestModel(
            code='github_auth_code',
            state='random_state',
            provider='github'
        )

        self.user_info: UserInfoModel = UserInfoModel(
            provider_id='github456',
            name='GitHub User',
            email='user@github.com',
            profile_picture_url='https://avatars.githubusercontent.com/u/456',
            provider=AuthProvider.GITHUB
        )

    def tearDown(self) -> None:
        """
        Close event loop.
        """
        self.loop.close()

    @patch('src.authentication.authentication_service.process_user_info')
    @patch.object(GithubAuthenticationService, 'fetch_user_info')
    def test_login_success(self, mock_fetch_user_info, mock_process_user_info) -> None:
        '''
        Test successful GitHub login flow.
        '''
        # Mock fetch_user_info
        mock_fetch_user_info.return_value = self.user_info

        # Mock process_user_info
        mock_session_response: SessionResponseModel = SessionResponseModel(
            session_id='test-session-456',
            user_info={'id': 2, 'name': 'GitHub User'},
            subscription_info={'id': 20, 'status': 'active'},
            current_subscription_plan={'id': 1, 'name': 'Free'}
        )
        mock_process_user_info.return_value = mock_session_response

        # Execute
        response: Response = self.loop.run_until_complete(self.service.login(self.request))

        # Assert
        self.assertEqual(response.status_code, 200)

        # Check that session cookie was set
        cookies: str = response.headers.get('set-cookie', '')
        self.assertIn('session=', cookies)

        # Check response body
        body: Dict[str, Any] = json.loads(response.body)
        self.assertEqual(body['session_id'], 'test-session-456')

    @patch.object(GithubAuthenticationService, 'fetch_user_info')
    def test_login_failure_no_user_info(self, mock_fetch_user_info) -> None:
        '''
        Test login failure when user info cannot be fetched.
        '''
        # Mock fetch_user_info returning None
        mock_fetch_user_info.return_value = None

        # Execute and assert exception
        with self.assertRaises(HTTPException) as context:
            self.loop.run_until_complete(self.service.login(self.request))

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn('Failed to fetch user information', context.exception.detail)

    @patch.object(GithubUserInfoService, 'get_credentials')
    @patch('httpx.AsyncClient')
    def test_fetch_user_info_success(self, mock_client_class, mock_get_credentials) -> None:
        '''
        Test successful user info fetch for GitHub.
        '''
        # Mock get_credentials
        from src.authentication.dto.oauth_credentials_dto import OAuthCredentialsModel
        mock_get_credentials.return_value = OAuthCredentialsModel(
            client_id='test_client',
            client_secret='test_secret',
            redirect_uri='https://example.com/callback',
            access_token_url='https://github.com/login/oauth/access_token',
            user_info_url='https://api.github.com/user',
            token_exchange_headers={'Accept': 'application/json'}
        )

        # Mock token exchange
        mock_token_response: MagicMock = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'github_token'
        }

        # Mock user info API
        mock_user_response: MagicMock = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            'id': 456,
            'name': 'Test User',
            'email': 'test@github.com',
            'avatar_url': 'https://avatars.githubusercontent.com/u/456'
        }

        mock_client: AsyncMock = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_token_response)
        mock_client.get = AsyncMock(return_value=mock_user_response)
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Execute
        result: UserInfoModel = self.loop.run_until_complete(self.service.fetch_user_info('test_code'))

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result.provider, AuthProvider.GITHUB)

    @patch('redis.Redis')
    def test_logout_success(self, mock_redis_class) -> None:
        '''
        Test successful logout.
        '''
        # Mock Redis
        mock_redis: MagicMock = MagicMock()
        mock_redis.delete = MagicMock(return_value=1)
        mock_redis_class.return_value = mock_redis

        # Execute
        response: Response = self.loop.run_until_complete(self.service.logout(session_id='test-session-123'))

        # Assert
        self.assertEqual(response.status_code, 200)

        # Check that session cookie was cleared
        cookies: str = response.headers.get('set-cookie', '')
        self.assertIn('max-age=0', cookies.lower())

        # Check response body
        body: Dict[str, Any] = json.loads(response.body)
        self.assertTrue(body['success'])
        self.assertEqual(body['message'], 'Logged out successfully')

    @patch('redis.Redis')
    def test_logout_without_session_id(self, mock_redis_class) -> None:
        '''
        Test logout without providing session ID.
        '''
        # Mock Redis
        mock_redis: MagicMock = MagicMock()
        mock_redis_class.return_value = mock_redis

        # Execute
        response: Response = self.loop.run_until_complete(self.service.logout())

        # Assert
        self.assertEqual(response.status_code, 200)

        # Should still clear the cookie
        cookies: str = response.headers.get('set-cookie', '')
        self.assertIn('max-age=0', cookies.lower())
