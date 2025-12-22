'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

import asyncio
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
import json
from typing import AsyncGenerator

from src.containers.containers_service import ContainerService
from src.data_models.containers import CreateContainerDBRequest, CreateContainerK8SRequest, ResourceLimits, UpdateContainerRequest, UpdateContainerFilters, UpdateContainerData, ListUserContainersRequest, DeleteContainerDBRequest, DeleteContainerK8SRequest
from src.data_models.echo import EchoRequestData, EchoResponseData
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.authentication_service import GoogleAuthenticationService, GithubAuthenticationService
from src.common.config import DB_CONFIG, NAMESPACE


# dtos
from src.authentication.dto.token_exchange_dto import TokenExchangeRequestModel
from src.status_listener import status_listener_service


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
async def create_container_in_db(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Creates a container in the database with PENDING status.
    This is the first step of the two-step container creation process.
    '''
    try:
        # get the create container request
        request_data: dict = await request.json()
        create_container_db_request: CreateContainerDBRequest = CreateContainerDBRequest(
            user_id=request_data['user_id'],
            image_id=request_data['image_id'],
            container_name=request_data['name'],
            cpu_limit=request_data.get('cpu_limit', '1'),
            memory_limit=request_data.get('memory_limit', '1Gi'),
            storage_limit=request_data.get('storage_limit', '2Gi'),
            publish_information=request_data.get('port_mappings', []),
            environment_variables=request_data.get('environment_variables', {})
        )
        # create a container in the database using ContainerService
        container_service = ContainerService()
        create_container_db_result: dict = await container_service.create_container_in_db(create_container_db_request)
        # return the response
        return JSONResponse(content=create_container_db_result)
    except HTTPException as e:
        # need to add logging here later
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        # need to add logging here later
        return JSONResponse(content={'error': f"Error creating container in database: {str(e)}"}, status_code=500)


@authenticate_session
async def create_container_in_k8s(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Creates a container in Kubernetes and updates the database record.
    This is the second step of the two-step container creation process.

    The status sidecar will update the container status via pg_notify,
    which will be pushed to the frontend via SSE.
    '''
    container_id = None
    try:
        request_data: dict = await request.json()

        # Extract required data
        container_id = request_data['container_id']
        resource_requirements = request_data.get('resource_requirements', {})

        # Build resource limits
        resource_limits = ResourceLimits(
            cpu_limit=resource_requirements.get('cpu_limit', '1'),
            memory_limit=resource_requirements.get('memory_limit', '1Gi'),
            storage_limit=resource_requirements.get('ephemeral_limit', '2Gi'),
            snapshot_size_limit=resource_requirements.get('snapshot_size_limit', '2Gi')
        )
        # Build FQDN for DB_HOST so status sidecar can access PostgreSQL from user namespace
        db_host_fqdn = f"{DB_CONFIG.host}.{NAMESPACE}.svc.cluster.local"
        environment_variables: dict = {
            **request_data.get('environment_variables', {}),
            **{
                'CONTAINER_ID': container_id,
                'DB_USERNAME': DB_CONFIG.username,
                'DB_PASSWORD': DB_CONFIG.password,
                'DB_NAME': DB_CONFIG.database,
                'DB_HOST': db_host_fqdn,
                'DB_PORT': str(DB_CONFIG.port),
                'DB_DATABASE': DB_CONFIG.database,
            }
        }
        # Build the K8S request
        create_container_k8s_request = CreateContainerK8SRequest(
            image_id=request_data['image_id'],
            container_name=request_data['container_name'],
            network_name=request_data['network_name'],
            exposure_level=request_data.get('exposure_level', 2),
            publish_information=request_data.get('publish_information', []),
            environment_variables=environment_variables,
            resource_limits=resource_limits
        )

        # Create container in K8s using ContainerService
        container_service = ContainerService()
        container_response = await container_service.create_container_in_k8s(create_container_k8s_request)
        return JSONResponse(content=container_response.model_dump())
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error creating container in Kubernetes: {str(e)}"}, status_code=500)


@authenticate_session
async def update_container(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Updates a container in the database.
    '''
    try:
        request_data: dict = await request.json()

        # Build filters
        filters_data = request_data.get('filters', {})
        filters = UpdateContainerFilters(
            container_id=filters_data.get('container_id'),
            user_id=filters_data.get('user_id'),
            kubernetes_id=filters_data.get('kubernetes_id'),
            name=filters_data.get('name')
        )

        # Build update data
        data_dict = request_data.get('data', {})
        data = UpdateContainerData(
            image_id=data_dict.get('image_id'),
            name=data_dict.get('name'),
            status=data_dict.get('status'),
            cpu_limit=data_dict.get('cpu_limit'),
            memory_limit=data_dict.get('memory_limit'),
            storage_limit=data_dict.get('storage_limit'),
            ip_address=data_dict.get('ip_address'),
            port_mappings=data_dict.get('port_mappings'),
            environment_vars=data_dict.get('environment_vars'),
            associated_resources=data_dict.get('associated_resources'),
            kubernetes_id=data_dict.get('kubernetes_id'),
            saved_image=data_dict.get('saved_image')
        )

        # Build the request
        update_request = UpdateContainerRequest(filters=filters, data=data)

        # Update via ContainerService
        container_service = ContainerService()
        result = await container_service.update_container(update_request)
        return JSONResponse(content=result)
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error updating container: {str(e)}"}, status_code=500)


@authenticate_session
async def list_user_containers(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Lists all containers for a specific user.
    '''
    try:
        user_id = request.query_params.get('user_id')
        if not user_id:
            return JSONResponse(content={'error': 'user_id is required'}, status_code=400)

        limit = request.query_params.get('limit')
        offset = request.query_params.get('offset')

        # Convert to int if provided
        limit = int(limit) if limit else None
        offset = int(offset) if offset else None

        list_containers_request = ListUserContainersRequest(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        container_service = ContainerService()
        containers = await container_service.list_user_containers(list_containers_request)
        return JSONResponse(content={'containers': containers})
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error listing containers: {str(e)}"}, status_code=500)


@authenticate_session
async def delete_container_in_db(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Deletes a container from the database.
    This is the first step of the two-step container deletion process.
    '''
    try:
        request_data: dict = await request.json()

        delete_container_db_request = DeleteContainerDBRequest(
            container_id=request_data['container_id'],
            user_id=request_data['user_id']
        )

        container_service = ContainerService()
        result = await container_service.delete_container_in_db(delete_container_db_request)
        return JSONResponse(content=result)
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error deleting container from database: {str(e)}"}, status_code=500)


@authenticate_session
async def delete_container_in_k8s(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Deletes a container from Kubernetes.
    This is the second step of the two-step container deletion process.
    '''
    try:
        request_data: dict = await request.json()

        delete_container_k8s_request = DeleteContainerK8SRequest(
            container_id=request_data['container_id'],
            network_name=request_data['network_name']
        )

        container_service = ContainerService()
        result = await container_service.delete_container_in_k8s(delete_container_k8s_request)
        return JSONResponse(content=result.model_dump())
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error deleting container from Kubernetes: {str(e)}"}, status_code=500)


@authenticate_session
async def container_status_sse(request: Request) -> StreamingResponse:
    """
    SSE endpoint for container status updates.
    Clients connect and receive real-time status changes for their containers.

    Query params:
        user_id: The user ID to subscribe to status updates for
    """
    user_id = request.query_params.get('user_id')
    if not user_id:
        return JSONResponse(content={'error': 'user_id is required'}, status_code=400)

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the status listener queue."""
        queue = status_listener_service.subscribe(user_id)
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for message with timeout (for keepalive)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f": keepalive\n\n"

        finally:
            status_listener_service.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
