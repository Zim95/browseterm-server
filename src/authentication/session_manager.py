'''
Redis Session Manager for multi-pod authentication.
Handles session storage and retrieval for distributed authentication.

To understand the implementation, read the following articles:
- Github Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-github-api-818383862591
- Google Login: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-google-apis-dead94d6866d

Handles - Creating, Retrieving, Updating, Deleting, Extending sessions.
'''

import json
import redis
import uuid
from typing import Optional, Dict, Any
from src.common.config import (
    REDIS_USERNAME, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, 
    REDIS_SESSION_PREFIX, REDIS_SESSION_EXPIRY
)
from src.authentication.dto.session_dto import SessionDataModel, SessionValidationModel
from src.authentication.enum.session_status_enum import SessionStatus


class RedisSessionManager:
    def __init__(self) -> None:
        """Initialize Redis connection."""
        self.redis_client: redis.Redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True
        )
        self.session_prefix: str = REDIS_SESSION_PREFIX
        self.session_expiry: int = REDIS_SESSION_EXPIRY

    def generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def create_session(self, session_data: SessionDataModel) -> str:
        """
        Create a new session with encoded session data.
        Args:
            session_data: SessionDataModel containing user info, subscription info, etc.
        Returns:
            str: Session ID
        """
        session_id: str = self.generate_session_id()
        session_key: str = f"{self.session_prefix}{session_id}"
        # Convert Pydantic model to dict and encode as JSON
        encoded_session_data: str = json.dumps(session_data.model_dump())
        # Store in Redis with expiry
        self.redis_client.setex(
            name=session_key, 
            time=self.session_expiry, 
            value=encoded_session_data
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionDataModel]:
        """
        Retrieve session data from session.
        Args:
            session_id: Session ID to retrieve
        Returns:
            SessionDataModel or None if not found
        """
        session_key: str = f"{self.session_prefix}{session_id}"
        try:
            encoded_session_data: str = self.redis_client.get(session_key)
            if encoded_session_data:
                session_dict: dict = json.loads(encoded_session_data)
                return SessionDataModel(**session_dict)
            return None
        except (json.JSONDecodeError, redis.RedisError) as e:
            print(f"Error retrieving session {session_id}: {e}")
            return None

    def update_session(self, session_id: str, session_data: SessionDataModel) -> bool:
        """
        Update existing session with new session data.
        Args:
            session_id: Session ID to update
            session_data: New session data
        Returns:
            bool: True if successful, False otherwise
        """
        session_key: str = f"{self.session_prefix}{session_id}"
        try:
            encoded_session_data: str = json.dumps(session_data.model_dump())
            self.redis_client.setex(
                name=session_key, 
                time=self.session_expiry, 
                value=encoded_session_data
            )
            return True
        except (json.JSONDecodeError, redis.RedisError) as e:
            print(f"Error updating session {session_id}: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        Args:
            session_id: Session ID to delete
        Returns:
            bool: True if successful, False otherwise
        """
        session_key: str = f"{self.session_prefix}{session_id}"
        try:
            result: bool = self.redis_client.delete(session_key)
            return result > 0
        except redis.RedisError as e:
            print(f"Error deleting session {session_id}: {e}")
            return False

    def extend_session(self, session_id: str, expiry: int | None = None) -> bool:
        """
        Extend session expiry.
        Args:
            session_id: Session ID to extend
            expiry: Expiry time in seconds
        Returns:
            bool: True if successful, False otherwise
        """
        session_key: str = f"{self.session_prefix}{session_id}"
        try:
            result: bool = self.redis_client.expire(session_key, expiry if expiry else self.session_expiry)
            return result
        except redis.RedisError as e:
            print(f"Error extending session {session_id}: {e}")
            return False

    def get_session_ttl(self, session_id: str) -> int:
        """
        Get the TTL of a session.
        Args:
            session_id: Session ID to check
        Returns:
            int: TTL in seconds if session exists and is not expired, -1 if session exists but has no expiry, -2 if session doesn't exist
        """
        session_key: str = f"{self.session_prefix}{session_id}"
        try:
            # Check TTL - returns -1 if key exists but has no expiry, -2 if key doesn't exist
            return self.redis_client.ttl(session_key)
        except redis.RedisError as e:
            print(f"Error checking session {session_id}: {e}")
            return -2

    def validate_session(self, session_id: str) -> SessionValidationModel:
        """
        Validate a session and return its status and data.
        Args:
            session_id: Session ID to validate
        Returns:
            SessionValidationModel with validation result
        """
        ttl: int = self.get_session_ttl(session_id)
        # Session doesn't exist
        if ttl == -2:
            return SessionValidationModel(is_valid=False, session_data=None, ttl=ttl)
        # Session expired (ttl == 0)
        if ttl == 0:
            self.delete_session(session_id)
            return SessionValidationModel(is_valid=False, session_data=None, ttl=ttl)
        # Session is valid (ttl > 0 or ttl == -1)
        session_data: Optional[SessionDataModel] = self.get_session(session_id)
        if not session_data:
            return SessionValidationModel(is_valid=False, session_data=None, ttl=ttl)        
        return SessionValidationModel(is_valid=True, session_data=session_data, ttl=ttl)


# Global session manager instance
session_manager: RedisSessionManager = RedisSessionManager()
