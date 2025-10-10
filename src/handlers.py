'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

import asyncio
from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
import json


from src.containers.containers_service import ContainerMakerClient
from src.containers.dto.create_container_dto import CreateContainerModel
from src.containers.dto.container_response_dto import ContainerResponseModel

from src.data_models.auth import TokenExchangeRequest
from src.data_models.echo import EchoRequestData, EchoResponseData
from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_AUTH_META_URL, GOOGLE_AUTH_SCOPE, GOOGLE_AUTH_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_AUTH_META_URL, GITHUB_AUTH_SCOPE, GITHUB_AUTH_REDIRECT_URI
)
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.oauth_service import GoogleUserInfoService, GithubUserInfoService
from src.common.config import REDIS_SESSION_EXPIRY
from src.authentication.authentication_helpers import process_user_info


templates = Jinja2Templates(directory="templates")


############################################ TEMPLATE ROUTES ############################################
@authenticate_session
async def home(request: Request) -> HTMLResponse:
    '''
    Home page template.
    '''
    return templates.TemplateResponse("home.html", {"request": request})


@authenticate_session
async def terminals(request: Request) -> HTMLResponse:
    '''
    Terminals page template.
    '''
    return templates.TemplateResponse("terminals.html", {"request": request})


@authenticate_session
async def subscriptions(request: Request) -> HTMLResponse:
    '''
    Subscriptions page template.
    '''
    return templates.TemplateResponse("subscriptions.html", {"request": request})


@authenticate_session
async def profile(request: Request) -> HTMLResponse:
    '''
    User profile page template.
    '''
    return templates.TemplateResponse(
        "profile.html", 
        {
            "request": request,
            "userInfo": request.state.user_info
        }
    )


async def login(request: Request) -> HTMLResponse:
    '''
    Login page template.
    '''
    return templates.TemplateResponse("login.html", {
        "request": request,
        "Google": {
            "client_id": GOOGLE_CLIENT_ID,
            "auth_meta_url": GOOGLE_AUTH_META_URL,
            "auth_scope": GOOGLE_AUTH_SCOPE,
            "auth_redirect_uri": GOOGLE_AUTH_REDIRECT_URI,
        },
        "Github": {
            "client_id": GITHUB_CLIENT_ID,
            "auth_meta_url": GITHUB_AUTH_META_URL,
            "auth_scope": GITHUB_AUTH_SCOPE,
            "auth_redirect_uri": GITHUB_AUTH_REDIRECT_URI,
        }
    })

############################################ AUTHENTICATION ROUTES ############################################

async def google_login_redirect(request: Request) -> HTMLResponse:
    '''
    Google login redirect page template.
    '''
    return templates.TemplateResponse("google_login_redirect.html", {"request": request})


async def github_login_redirect(request: Request) -> HTMLResponse:
    '''
    Github login redirect page template.
    '''
    return templates.TemplateResponse("github_login_redirect.html", {"request": request})


async def google_token_exchange(request: TokenExchangeRequest) -> Response:
    '''
    Exchange Google OAuth code for tokens, fetch user details and create session.
    '''
    try:
        user_info: dict = await GoogleUserInfoService().fetch_user_info(request.code)
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to exchange Google token")
        response_data: dict = await process_user_info(user_info)
        if not response_data['session_id']:
            raise HTTPException(status_code=500, detail="Failed to create session")
        response = Response(
            content=json.dumps(response_data),
            media_type="application/json",
            status_code=200
        )
        response.set_cookie(
            key="session",
            value=response_data['session_id'],
            max_age=REDIS_SESSION_EXPIRY,
            httponly=True,
            secure=True,
            samesite="strict"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Google token exchange error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def github_token_exchange(request: TokenExchangeRequest) -> Response:
    '''
    Exchange GitHub OAuth code for tokens and create session.
    '''
    try:
        user_info = await GithubUserInfoService().fetch_user_info(request.code)
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to exchange GitHub token")
        response_data: dict = await process_user_info(user_info)
        if not response_data['session_id']:
            raise HTTPException(status_code=500, detail="Failed to create session")
        response = Response(
            content=json.dumps(response_data),
            media_type="application/json",
            status_code=200
        )
        response.set_cookie(
            key="session",
            value=response_data['session_id'],
            max_age=REDIS_SESSION_EXPIRY,
            httponly=True,
            secure=True,
            samesite="strict"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"GitHub token exchange error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def logout() -> Response:
    '''
    Logout user by clearing session cookie and removing from Redis.
    '''
    try:
        response = Response(
            content=json.dumps({"message": "Logged out successfully"}),
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


############################################ API ROUTES ############################################

async def echo(request: EchoRequestData) -> EchoResponseData:
    '''
    Simply echo the request message.
    '''
    return EchoResponseData(message=request.message)


async def create_container(request: CreateContainerModel) -> ContainerResponseModel:
    '''
    Authentication: This handler needs to be authenticated.
    Creates an SSH container and a Socket-SSH container.
    '''
    try:
        # create a container maker client
        container_maker_client: ContainerMakerClient = ContainerMakerClient()
        # create a container
        container_response_model: ContainerResponseModel = await container_maker_client.create_container(request)
        # return the response
        return container_response_model
    except Exception as e:
        raise e
