'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

import asyncio
from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
import json


from src.containers.containers_service import ContainerService
from src.containers.dto.create_container_dto import CreateContainerModel
from src.containers.dto.container_response_dto import ContainerResponseModel

from src.data_models.echo import EchoRequestData, EchoResponseData
from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_AUTH_META_URL, GOOGLE_AUTH_SCOPE, GOOGLE_AUTH_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_AUTH_META_URL, GITHUB_AUTH_SCOPE, GITHUB_AUTH_REDIRECT_URI
)
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.authentication_service import GoogleAuthenticationService, GithubAuthenticationService
from src.db_ops.subscription_db_ops import list_all_existing_subscription_types

# dtos
from src.authentication.dto.token_exchange_dto import TokenExchangeRequestModel


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


# NEW: Terminal page template
@authenticate_session
async def terminalpage(request: Request) -> HTMLResponse:
    '''
    Terminal page template - shows xterm.js terminal with ad banners.
    '''
    # Get terminal ID from query params
    terminal_id = request.query_params.get('id', '')
    # TODO: In production, fetch actual terminal info from database using terminal_id
    # For now, using dummy data
    terminal_info = {
        "id": terminal_id,
        "name": f"Terminal {terminal_id}",
        "ipAddress": "192.168.1.100",
        "port": "8080"
    }
    return templates.TemplateResponse(
        "terminalpage.html",
        {
            "request": request,
            "terminalInfo": terminal_info
        }
    )


@authenticate_session
async def subscriptions(request: Request) -> HTMLResponse:
    '''
    Subscriptions page template.
    '''
    subscriptions: list = await asyncio.to_thread(list_all_existing_subscription_types)
    return templates.TemplateResponse(
        "subscriptions.html",
        {
            "request": request,
            "subscriptions": subscriptions,
            "userInfo": request.state.user_info,
            "subscriptionInfo": request.state.subscription_info,
            "currentSubscriptionPlan": request.state.current_subscription_plan
        }
    )


@authenticate_session
async def profile(request: Request) -> HTMLResponse:
    '''
    User profile page template.
    '''
    return templates.TemplateResponse(
        "profile.html", 
        {
            "request": request,
            "userInfo": request.state.user_info,
            "subscriptionInfo": request.state.subscription_info,
            "currentSubscriptionPlan": request.state.current_subscription_plan
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


async def google_token_exchange(request: TokenExchangeRequestModel) -> Response:
    '''
    Exchange Google OAuth code for tokens, fetch user details and create session.
    Uses GoogleAuthenticationService following Open-Closed Principle.
    '''
    auth_service: GoogleAuthenticationService = GoogleAuthenticationService()
    return await auth_service.login(request)


async def github_token_exchange(request: TokenExchangeRequestModel) -> Response:
    '''
    Exchange GitHub OAuth code for tokens and create session.
    Uses GithubAuthenticationService following Open-Closed Principle.
    '''
    auth_service: GithubAuthenticationService = GithubAuthenticationService()
    return await auth_service.login(request)


async def logout() -> Response:
    '''
    Logout user by clearing session cookie and removing from Redis.
    Uses GoogleAuthenticationService (can use any auth service for logout).
    '''
    auth_service: GoogleAuthenticationService = GoogleAuthenticationService()
    return await auth_service.logout()


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
        container_maker_client: ContainerService = ContainerService()
        # create a container
        container_response_model: ContainerResponseModel = await container_maker_client.create_container(request)
        # return the response
        return container_response_model
    except Exception as e:
        raise e
