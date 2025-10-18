# builtins
from unittest import TestCase
from typing import Dict, Any, Optional
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# local
from src.authentication.authentication_helpers import (
    create_session,
    extend_session,
    process_user_info,
    authenticate_session
)
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.dto.session_dto import SessionDataModel, SessionResponseModel
from browseterm_db.models.users import AuthProvider
from fastapi import Request
from fastapi.responses import RedirectResponse


class TestAuthenticationHelpers(TestCase):
    '''
    Test authentication helper functions with mocked dependencies.
    Tests session creation, extension, user processing, and authentication decorator.
    '''

    def setUp(self) -> None:
        '''
        Setup test data.
        '''
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.user_info: UserInfoModel = UserInfoModel(
            provider_id='test123',
            name='Test User',
            email='test@example.com',
            profile_picture_url='https://example.com/pic.jpg',
            provider=AuthProvider.GOOGLE
        )

        self.session_data: SessionDataModel = SessionDataModel(
            user_info={'id': 1, 'name': 'Test User'},
            subscription_info={'id': 10, 'status': 'active'},
            current_subscription_plan={'id': 1, 'name': 'Free'}
        )

    def tearDown(self) -> None:
        """
        Close event loop.
        """
        self.loop.close()

    @patch('redis.Redis')
    def test_create_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session creation.
        '''
        # Mock Redis
        mock_redis: MagicMock = MagicMock()
        mock_redis.setex = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Execute
        session_id: str = create_session(self.session_data)

        # Assert
        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, str)

    @patch('redis.Redis')
    def test_create_session_failure(self, mock_redis_class) -> None:
        '''
        Test session creation failure.
        '''
        # Mock Redis to raise exception
        mock_redis: MagicMock = MagicMock()
        mock_redis.setex = MagicMock(side_effect=Exception('Redis connection failed'))
        mock_redis_class.return_value = mock_redis

        # Execute and assert exception
        with self.assertRaises(Exception) as context:
            create_session(self.session_data)

        self.assertIn('Error creating session', str(context.exception))

    @patch('redis.Redis')
    def test_extend_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session extension.
        '''
        # Mock Redis
        mock_redis: MagicMock = MagicMock()
        mock_redis.expire = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Execute (should not raise exception)
        extend_session('test-session-123', expiry=1800)

        # If we get here without exception, test passes
        self.assertTrue(True)

    @patch('redis.Redis')
    def test_extend_session_failure(self, mock_redis_class) -> None:
        '''
        Test session extension failure.
        '''
        # Mock Redis to raise exception
        mock_redis: MagicMock = MagicMock()
        mock_redis.expire = MagicMock(side_effect=Exception('Redis connection failed'))
        mock_redis_class.return_value = mock_redis

        # Execute and assert exception
        with self.assertRaises(Exception) as context:
            extend_session('test-session-123', expiry=1800)

        self.assertIn('Error extending session', str(context.exception))

    @patch('src.authentication.authentication_helpers.create_session')
    @patch('src.authentication.authentication_helpers.get_current_subscription_plan')
    @patch('src.authentication.authentication_helpers.get_or_create_free_subscription')
    @patch('src.authentication.authentication_helpers.create_or_update_user')
    def test_process_user_info_success(
        self,
        mock_create_user,
        mock_get_subscription,
        mock_get_plan,
        mock_create_session
    ) -> None:
        '''
        Test successful user info processing.
        '''
        # Mock database operations
        mock_create_user.return_value: Dict[str, Any] = {
            'id': 1,
            'provider_id': 'test123',
            'name': 'Test User',
            'email': 'test@example.com',
            'provider': 'google'
        }

        mock_get_subscription.return_value: Dict[str, Any] = {
            'id': 10,
            'user_id': 1,
            'subscription_type_id': 1,
            'status': 'active'
        }

        mock_get_plan.return_value: Dict[str, Any] = {
            'id': 1,
            'name': 'Free',
            'price': 0
        }

        mock_create_session.return_value = 'test-session-123'

        # Execute
        result: SessionResponseModel = self.loop.run_until_complete(process_user_info(self.user_info))

        # Assert
        self.assertIsInstance(result, SessionResponseModel)
        self.assertEqual(result.session_id, 'test-session-123')
        self.assertEqual(result.user_info['id'], 1)
        self.assertEqual(result.subscription_info['id'], 10)
        self.assertEqual(result.current_subscription_plan['id'], 1)

    @patch('src.authentication.authentication_helpers.create_or_update_user')
    def test_process_user_info_failure(self, mock_create_user) -> None:
        '''
        Test user info processing failure.
        '''
        # Mock database operation to fail
        mock_create_user.side_effect = Exception('Database error')

        # Execute and assert exception
        with self.assertRaises(Exception) as context:
            self.loop.run_until_complete(process_user_info(self.user_info))

        self.assertIn('Error processing user info', str(context.exception))

    @patch('redis.Redis')
    def test_authenticate_session_decorator_success(self, mock_redis_class) -> None:
        '''
        Test authenticate_session decorator with valid session.
        '''
        import json

        # Mock Redis with valid session
        session_data: Dict[str, Any] = {
            'user_info': {'id': 1, 'name': 'Test User'},
            'subscription_info': {'id': 10},
            'current_subscription_plan': {'id': 1}
        }

        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=1800)  # Valid session
        mock_redis.get = MagicMock(return_value=json.dumps(session_data))
        mock_redis.expire = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Create a test handler
        @authenticate_session
        async def test_handler(request: Request):
            return {'message': 'success', 'user_id': request.state.user_info['id']}

        # Create mock request with session cookie
        mock_request: MagicMock = MagicMock(spec=Request)
        mock_request.cookies = {'session': 'valid-session-123'}
        mock_request.state = MagicMock()

        # Execute
        result: Dict[str, Any] = self.loop.run_until_complete(test_handler(request=mock_request))

        # Assert
        self.assertEqual(result['message'], 'success')
        self.assertEqual(result['user_id'], 1)

    @patch('redis.Redis')
    def test_authenticate_session_decorator_no_cookie(self, mock_redis_class) -> None:
        '''
        Test authenticate_session decorator without session cookie.
        '''
        # Create a test handler
        @authenticate_session
        async def test_handler(request: Request):
            return {'message': 'success'}

        # Create mock request without session cookie
        mock_request: MagicMock = MagicMock(spec=Request)
        mock_request.cookies = {}

        # Execute
        result: Dict[str, Any] = self.loop.run_until_complete(test_handler(request=mock_request))

        # Assert - should redirect to login
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 302)
        self.assertIn('/login', result.headers['location'])

    @patch('redis.Redis')
    def test_authenticate_session_decorator_expired_session(self, mock_redis_class) -> None:
        '''
        Test authenticate_session decorator with expired session.
        '''
        # Mock Redis with expired session
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=0)  # Expired
        mock_redis.delete = MagicMock(return_value=1)
        mock_redis_class.return_value = mock_redis

        # Create a test handler
        @authenticate_session
        async def test_handler(request: Request):
            return {'message': 'success'}

        # Create mock request with session cookie
        mock_request: MagicMock = MagicMock(spec=Request)
        mock_request.cookies = {'session': 'expired-session-123'}

        # Execute
        result: Dict[str, Any] = self.loop.run_until_complete(test_handler(request=mock_request))

        # Assert - should redirect to login
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 302)
        self.assertIn('/login', result.headers['location'])

    @patch('redis.Redis')
    def test_authenticate_session_decorator_invalid_session(self, mock_redis_class) -> None:
        '''
        Test authenticate_session decorator with non-existent session.
        '''
        # Mock Redis with non-existent session
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=-2)  # Key doesn't exist
        mock_redis_class.return_value = mock_redis

        # Create a test handler
        @authenticate_session
        async def test_handler(request: Request):
            return {'message': 'success'}

        # Create mock request with session cookie
        mock_request: MagicMock = MagicMock(spec=Request)
        mock_request.cookies = {'session': 'invalid-session-123'}

        # Execute
        result: Dict[str, Any] = self.loop.run_until_complete(test_handler(request=mock_request))

        # Assert - should redirect to login
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 302)
        self.assertIn('/login', result.headers['location'])
