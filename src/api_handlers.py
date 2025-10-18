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
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.authentication_service import GoogleAuthenticationService, GithubAuthenticationService


# dtos
from src.authentication.dto.token_exchange_dto import TokenExchangeRequestModel


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


async def echo(request: EchoRequestData) -> EchoResponseData:
    '''
    Simply echo the request message.
    '''
    return EchoResponseData(message=request.message)


@authenticate_session
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
