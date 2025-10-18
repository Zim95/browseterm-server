from pydantic import BaseModel
from typing import Optional
from browseterm_db.models.users import AuthProvider


class UserInfoModel(BaseModel):
    '''
    Standardized user information model
    '''
    provider_id: str  # ID from OAuth provider
    name: Optional[str] = None
    email: Optional[str] = None
    profile_picture_url: Optional[str] = None
    provider: AuthProvider  # Which provider (Google, GitHub, etc.)


class UserInfoResponseModel(BaseModel):
    '''
    User information response model (includes database ID)
    '''
    id: int  # Database user ID
    provider_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    profile_picture_url: Optional[str] = None
    provider: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
