'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

import asyncio
from fastapi import Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from src.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_AUTH_META_URL, GOOGLE_AUTH_SCOPE, GOOGLE_AUTH_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_AUTH_META_URL, GITHUB_AUTH_SCOPE, GITHUB_AUTH_REDIRECT_URI,
    SOCKET_SSH_WSS_URL
)
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.session_manager import session_manager
from src.db_ops.image_db_ops import list_all_existing_images
from src.db_ops.subscription_db_ops import list_all_existing_subscription_types
from src.db_ops.container_db_ops import get_container
from src.db_ops.dto.container_dto import GetContainerDBModel
from src.common.logging_setup import get_logger

logger = get_logger("template_handlers")


templates = Jinja2Templates(directory="templates")


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
    subscriptions: list = await list_all_existing_subscription_types()
    images: list = await list_all_existing_images()
    return templates.TemplateResponse(
        "terminals.html",
        {
            "request": request,
            "subscriptions": subscriptions,
            "images": images,
            "userInfo": request.state.user_info,
            "currentSubscriptionPlan": request.state.current_subscription_plan
        }
    )


@authenticate_session
async def terminalpage(request: Request) -> HTMLResponse:
    '''
    Terminal page template - shows xterm.js terminal with ad banners.
    '''
    # Get terminal ID from query params
    terminal_id = request.query_params.get('id', '')

    if not terminal_id:
        # If no terminal ID provided, show error page
        terminal_info = {
            "id": "",
            "name": "Error",
            "ipAddress": "N/A",
            "port": "N/A",
            "error": "No terminal ID provided"
        }
    else:
        try:
            # Fetch actual terminal info from database
            get_container_data = GetContainerDBModel(
                container_id=terminal_id,
                user_id=request.state.user_info['id']  # user_info is a dict
            )
            container_data = await get_container(get_container_data)
            
            if not container_data:
                terminal_info = {
                    "id": terminal_id,
                    "name": "Not Found",
                    "ipAddress": "N/A",
                    "port": "N/A",
                    "error": "Terminal not found or you don't have access"
                }
            else:
                # Extract SSH credentials from environment variables
                env_vars = container_data.get('environment_vars', {})  # DB column is environment_vars
                ssh_username = env_vars.get('SSH_USERNAME', '')
                ssh_password = env_vars.get('SSH_PASSWORD', '')
                
                # Get port from port_mappings
                port_mappings = container_data.get('port_mappings', [])
                ssh_port = port_mappings[0].get('publish_port') if port_mappings else 2222
                
                terminal_info = {
                    "id": container_data.get('id'),
                    "name": container_data.get('name'),
                    "ipAddress": container_data.get('ip_address', 'Pending...'),
                    "port": str(ssh_port),
                    "sshUsername": ssh_username,
                    "sshPassword": ssh_password,
                    "status": container_data.get('status', 'Unknown')
                }
        except Exception as e:
            logger.error("error fetching terminal info", extra={"container_id": terminal_id}, exc_info=True)
            terminal_info = {
                "id": terminal_id,
                "name": "Error",
                "ipAddress": "N/A",
                "port": "N/A",
                "error": f"Error loading terminal: {str(e)}"
            }
    
    # Generate one-time WebSocket token for this session
    session_id = request.cookies.get('session')
    ws_token = session_manager.create_websocket_token(session_id) if session_id else ''
    return templates.TemplateResponse(
        "terminalpage.html",
        {
            "request": request,
            "terminalInfo": terminal_info,
            "socketSSHUrl": SOCKET_SSH_WSS_URL,
            "wsToken": ws_token,
            "userInfo": request.state.user_info
        }
    )


@authenticate_session
async def subscriptions(request: Request) -> HTMLResponse:
    '''
    Subscriptions page template.
    '''
    subscriptions: list = await list_all_existing_subscription_types()
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


async def js_test(request: Request) -> HTMLResponse:
    '''
    JavaScript test runner page.
    Hidden route - not in sidebar navigation.
    '''
    return templates.TemplateResponse("js_test.html", {"request": request})
