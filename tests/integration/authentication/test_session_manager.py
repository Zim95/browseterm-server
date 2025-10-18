# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock
import json

# local
from src.authentication.session_manager import RedisSessionManager
from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel


class TestRedisSessionManager(TestCase):
    '''
    Test RedisSessionManager with mocked Redis.
    Tests session creation, retrieval, update, deletion, and validation.
    '''

    def setUp(self) -> None:
        '''
        Setup test data for session management.
        '''
        self.session_data: SessionDataModel = SessionDataModel(
            user_info={'id': 1, 'name': 'Test User', 'email': 'test@example.com'},
            subscription_info={'id': 10, 'status': 'active'},
            current_subscription_plan={'id': 1, 'name': 'Free'}
        )

        self.session_id: str = 'test-session-id-123'

    @patch('redis.Redis')
    def test_create_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session creation.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.setex = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        session_id: str = session_manager.create_session(self.session_data)

        # Assert
        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, str)
        mock_redis.setex.assert_called_once()

    @patch('redis.Redis')
    def test_get_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session retrieval.
        '''
        # Mock Redis client with stored session data
        encoded_data: str = json.dumps(self.session_data.model_dump())
        mock_redis: MagicMock = MagicMock()
        mock_redis.get = MagicMock(return_value=encoded_data)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        retrieved_session: SessionDataModel | None = session_manager.get_session(self.session_id)

        # Assert
        self.assertIsNotNone(retrieved_session)
        self.assertIsInstance(retrieved_session, SessionDataModel)
        self.assertEqual(retrieved_session.user_info, self.session_data.user_info)
        self.assertEqual(retrieved_session.subscription_info, self.session_data.subscription_info)

    @patch('redis.Redis')
    def test_get_session_not_found(self, mock_redis_class) -> None:
        '''
        Test session retrieval when session doesn't exist.
        '''
        # Mock Redis client returning None
        mock_redis: MagicMock = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        retrieved_session: SessionDataModel | None = session_manager.get_session('non-existent-session')

        # Assert
        self.assertIsNone(retrieved_session)

    @patch('redis.Redis')
    def test_update_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session update.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.setex = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        result: bool = session_manager.update_session(self.session_id, self.session_data)

        # Assert
        self.assertTrue(result)
        mock_redis.setex.assert_called_once()

    @patch('redis.Redis')
    def test_delete_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session deletion.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.delete = MagicMock(return_value=1)  # 1 means key was deleted
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        result: bool = session_manager.delete_session(self.session_id)

        # Assert
        self.assertTrue(result)
        mock_redis.delete.assert_called_once()

    @patch('redis.Redis')
    def test_delete_session_not_found(self, mock_redis_class) -> None:
        '''
        Test session deletion when session doesn't exist.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.delete = MagicMock(return_value=0)  # 0 means key was not found
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        result: bool = session_manager.delete_session('non-existent-session')

        # Assert
        self.assertFalse(result)

    @patch('redis.Redis')
    def test_extend_session_success(self, mock_redis_class) -> None:
        '''
        Test successful session TTL extension.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.expire = MagicMock(return_value=True)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        result: bool = session_manager.extend_session(self.session_id, expiry=3600)

        # Assert
        self.assertTrue(result)
        mock_redis.expire.assert_called_once()

    @patch('redis.Redis')
    def test_get_session_ttl_active(self, mock_redis_class) -> None:
        '''
        Test getting TTL of an active session.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=1800)  # 30 minutes remaining
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        ttl: int = session_manager.get_session_ttl(self.session_id)

        # Assert
        self.assertEqual(ttl, 1800)

    @patch('redis.Redis')
    def test_get_session_ttl_not_found(self, mock_redis_class) -> None:
        '''
        Test getting TTL when session doesn't exist.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=-2)  # -2 means key doesn't exist
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        ttl: int = session_manager.get_session_ttl('non-existent-session')

        # Assert
        self.assertEqual(ttl, -2)

    @patch('redis.Redis')
    def test_validate_session_valid(self, mock_redis_class) -> None:
        '''
        Test session validation for a valid session.
        '''
        # Mock Redis client
        encoded_data: str = json.dumps(self.session_data.model_dump())
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=1800)  # Active session
        mock_redis.get = MagicMock(return_value=encoded_data)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        validation: SessionValidationModel = session_manager.validate_session(self.session_id)

        # Assert
        self.assertIsInstance(validation, SessionValidationModel)
        self.assertTrue(validation.is_valid)
        self.assertIsNotNone(validation.session_data)
        self.assertEqual(validation.ttl, 1800)

    @patch('redis.Redis')
    def test_validate_session_not_found(self, mock_redis_class) -> None:
        '''
        Test session validation when session doesn't exist.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=-2)  # Session doesn't exist
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        validation: SessionValidationModel = session_manager.validate_session('non-existent-session')

        # Assert
        self.assertFalse(validation.is_valid)
        self.assertIsNone(validation.session_data)

    @patch('redis.Redis')
    def test_validate_session_expired(self, mock_redis_class) -> None:
        '''
        Test session validation for an expired session.
        '''
        # Mock Redis client
        mock_redis: MagicMock = MagicMock()
        mock_redis.ttl = MagicMock(return_value=0)  # Expired session
        mock_redis.delete = MagicMock(return_value=1)
        mock_redis_class.return_value = mock_redis

        # Create session manager
        session_manager: RedisSessionManager = RedisSessionManager()
        session_manager.redis_client = mock_redis

        # Execute
        validation: SessionValidationModel = session_manager.validate_session(self.session_id)

        # Assert
        self.assertFalse(validation.is_valid)
        self.assertIsNone(validation.session_data)
        mock_redis.delete.assert_called_once()  # Should delete expired session
