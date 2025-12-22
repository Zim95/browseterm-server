'''
User database operation DTOs.
'''

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class CreateOrUpdateUserModel(BaseModel):
    """
    Model for creating or updating a user from OAuth provider.

    Fields based on browseterm_db User model:
    - provider_id: Unique ID from the OAuth provider (required)
    - provider: OAuth provider - 'google' or 'github' (required)
    - name: User's display name (optional, but typically provided by OAuth)
    - email: User's email address (optional, but typically provided by OAuth)
    - profile_picture_url: URL to user's profile picture (optional)
    - last_login: Timestamp of last login (optional, set during login)
    - is_active: Whether the account is active (default True, for soft delete)
    """
    provider_id: str
    provider: str  # 'google' or 'github'
    name: Optional[str] = None
    email: Optional[str] = None
    profile_picture_url: Optional[str] = None
    last_login: Optional[datetime] = None
    is_active: Optional[bool] = True

    def to_dict(self):
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class GetUserModel(BaseModel):
    """Model for getting a user by provider info."""
    provider_id: str
    provider: str
