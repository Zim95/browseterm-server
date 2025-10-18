'''
Authentication Service.
Main orchestrator for authentication operations.
Handles OAuth login, session management, and user authentication.
'''

# builtins
import asyncio
from typing import Optional

# fastapi
from fastapi import Request, HTTPException
from fastapi.responses import Response
import json

# local services
from src.authentication.oauth_service import GoogleUserInfoService, GithubUserInfoService
from src.authentication.session_manager import RedisSessionManager
from src.authentication.authentication_helpers import process_user_info, extend_session

# dtos
from src.authentication.dto.user_info_dto import UserInfoModel
from src.authentication.dto.token_exchange_dto import TokenExchangeRequestModel
from src.authentication.dto.session_dto import SessionResponseModel, SessionValidationModel
from src.authentication.dto.login_response_dto import LoginResponseModel
from src.authentication.dto.logout_dto import LogoutResponseModel

# config
from src.common.config import REDIS_SESSION_EXPIRY


class AuthenticationService:
    '''
    Main authentication service orchestrator.
    Handles all authentication-related operations.
    '''

    def __init__(self) -> None:
        '''
        Initialize the authentication service.
        '''
        self.session_manager: RedisSessionManager = RedisSessionManager()
        self.google_service: GoogleUserInfoService = GoogleUserInfoService()
        self.github_service: GithubUserInfoService = GithubUserInfoService()

    async def fetch_user_info(self, code: str) -> Optional[UserInfoModel]:
        '''
        Fetch user info from the provider.
        Must be implemented by subclasses.
        '''
        raise NotImplementedError("Please implement fetch_user_info!")

    async def login(self, request: TokenExchangeRequestModel) -> Response:
        '''
        Handle OAuth login flow.
        1. Exchange code for user info (provider-specific via fetch_user_info)
        2. Create or update user in database
        3. Create session
        4. Return response with session cookie
        Args:
            request: TokenExchangeRequestModel containing OAuth code
        Returns:
            Response with session cookie and user data
        Raises:
            HTTPException: On authentication failure
        '''
        try:
            # Fetch user info from the provider
            user_info: Optional[UserInfoModel] = await self.fetch_user_info(request.code)
            if not user_info:
                raise HTTPException(status_code=400, detail="Failed to exchange token")
            # Process user info and create session
            session_response: SessionResponseModel = await process_user_info(user_info)
            if not session_response.session_id:
                raise HTTPException(status_code=500, detail="Failed to create session")
            # Create response with session cookie
            response_data: dict = session_response.model_dump()
            response = Response(
                content=json.dumps(response_data),
                media_type="application/json",
                status_code=200
            )
            response.set_cookie(
                key="session",
                value=session_response.session_id,
                max_age=REDIS_SESSION_EXPIRY,
                httponly=True,
                secure=True,
                samesite="strict"
            )
            return response
        except HTTPException:
            raise
        except Exception as e:
            print(f"Login error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def logout(self, session_id: Optional[str] = None) -> Response:
        '''
        Handle user logout.
        1. Delete session from Redis
        2. Clear session cookie
        Args:
            session_id: Optional session ID to delete
        Returns:
            Response with cleared cookie
        Raises:
            HTTPException: On logout failure
        '''
        try:
            # Delete session from Redis if session_id provided
            if session_id:
                self.session_manager.delete_session(session_id)
            # Create logout response
            logout_data: LogoutResponseModel = LogoutResponseModel(
                message="Logged out successfully",
                success=True
            )
            response = Response(
                content=json.dumps(logout_data.model_dump()),
                media_type="application/json",
                status_code=200
            )
            response.set_cookie(
                key="session",
                value="",
                max_age=0,
                httponly=True,
                secure=True,
                samesite="strict"
            )
            return response
        except Exception as e:
            print(f"Logout error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    def validate_session(self, session_id: str) -> SessionValidationModel:
        '''
        Validate a session.
        
        Args:
            session_id: Session ID to validate
        Returns:
            SessionValidationModel with validation result
        '''
        return self.session_manager.validate_session(session_id)

    def extend_session_ttl(self, session_id: str, expiry: Optional[int] = None) -> None:
        '''
        Extend session TTL.
        
        Args:
            session_id: Session ID to extend
            expiry: Optional expiry time in seconds
        '''
        extend_session(session_id, expiry)


class GoogleAuthenticationService(AuthenticationService):
    '''
    Google authentication service.
    Handles all Google authentication-related operations.
    '''
    def __init__(self) -> None:
        '''
        Initialize the Google authentication service.
        '''
        super().__init__()

    async def fetch_user_info(self, code: str) -> Optional[UserInfoModel]:
        '''
        Fetch user info from Google.
        '''
        return await self.google_service.fetch_user_info(code)


class GithubAuthenticationService(AuthenticationService):
    '''
    Github authentication service.
    Handles all Github authentication-related operations.
    '''
    def __init__(self) -> None:
        '''
        Initialize the Github authentication service.
        '''
        super().__init__()

    async def fetch_user_info(self, code: str) -> Optional[UserInfoModel]:
        '''
        Fetch user info from Github.
        '''
        return await self.github_service.fetch_user_info(code)
