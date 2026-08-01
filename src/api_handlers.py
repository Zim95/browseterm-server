'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

import asyncio
from datetime import datetime, timezone
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
import json
from typing import AsyncGenerator

from src.containers.containers_service import ContainerService
from src.data_models.containers import CreateContainerDBRequest, CreateContainerK8SRequest, GetContainerRequest, ResourceLimits, UpdateContainerRequest, UpdateContainerFilters, UpdateContainerData, ListUserContainersRequest, DeleteContainerDBRequest, DeleteContainerK8SRequest, SaveContainerK8SRequest
from browseterm_db.operations.all_operations import ContainerOps
from browseterm_db.models.containers import SaveStatus, ContainerStatus
from src.data_models.echo import EchoRequestData, EchoResponseData
from src.authentication.authentication_helpers import authenticate_session
from src.authentication.authentication_service import GoogleAuthenticationService, GithubAuthenticationService
from src.common.config import DB_CONFIG, NAMESPACE
from src.common.logging_setup import get_logger, request_id_var

logger = get_logger("api_handlers")


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
async def get_container_info(request: Request) -> JSONResponse:
    '''
    Authentication: This handler needs to be authenticated.
    Gets container info by container ID.
    '''
    try:
        # build the get container request
        get_container_request: GetContainerRequest = GetContainerRequest(
            container_id=request.path_params,
            user_id=request.state.user_info.id  # user_id will be extracted from session in ContainerService
        )
        # get container info using ContainerService
        container_service = ContainerService()
        container_info: dict = await container_service.get_container_info(get_container_request)
        return JSONResponse(content=container_info)
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error getting container info: {str(e)}"}, status_code=500)

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
        # No DB credentials are injected into the user pod. Status is written by the central
        # status_monitor (which reads pod phase from the k8s API), not by an in-pod sidecar, so the
        # untrusted user pod never receives database credentials. CONTAINER_ID is passed only so
        # container-maker can stamp it as the browseterm/container-id pod label the monitor reads.
        environment_variables: dict = {
            **request_data.get('environment_variables', {}),
            'CONTAINER_ID': container_id,
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

        # Note: The frontend sends 'container_id' but it's actually the kubernetes_id (pod UID)
        # The naming is confusing but we maintain backward compatibility with frontend
        delete_container_k8s_request = DeleteContainerK8SRequest(
            container_id=request_data['container_id'],  # This is the pod UID from K8s
            network_name=request_data['network_name']
        )

        container_service = ContainerService()
        result = await container_service.delete_container_in_k8s(delete_container_k8s_request)
        return JSONResponse(content=result.model_dump())
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error deleting container from Kubernetes: {str(e)}"}, status_code=500)


async def _set_save_status(container_id: str, save_status: str, save_error: str = None) -> None:
    """Update a container's save_status/save_error in the DB. The save-status trigger fires the SSE."""
    ops = ContainerOps(DB_CONFIG)
    await asyncio.to_thread(
        ops.update,
        filters={"id": container_id},
        data={"save_status": save_status, "save_error": save_error, "last_request_id": request_id_var.get()},
    )


async def _run_save(container_service, save_request, container_id: str) -> None:
    """Background task: run the (blocking) gRPC save. The Job records SUCCEEDED/FAILED via the DB;
    if the gRPC call itself fails before the Job records anything, mark FAILED here."""
    try:
        await container_service.save_container_in_k8s(save_request)
    except Exception as e:
        try:
            await _set_save_status(container_id, SaveStatus.FAILED.value, save_error=str(e)[:1000])
        except Exception as db_e:
            logger.error("failed to record save failure", extra={"container_id": container_id}, exc_info=True)


@authenticate_session
async def save_container(request: Request) -> JSONResponse:
    '''
    Authentication required. Triggers an asynchronous container save/snapshot.
    Sets save_status=PENDING immediately and fires the save in the background; progress is
    delivered to the frontend via the container status SSE ('save_status_change' events).
    '''
    try:
        request_data: dict = await request.json()
        container_id = request_data['container_id']   # DB container id
        network_name = request_data['network_name']

        # Mark PENDING now so the frontend can show the spinner immediately.
        await _set_save_status(container_id, SaveStatus.PENDING.value)

        save_request = SaveContainerK8SRequest(container_id=container_id, network_name=network_name)
        container_service = ContainerService()

        # container-maker blocks until the snapshot Job completes, so run it in the background.
        asyncio.create_task(_run_save(container_service, save_request, container_id))

        return JSONResponse(content={'status': 'pending', 'container_id': container_id}, status_code=202)
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={'error': f"Error starting container save: {str(e)}"}, status_code=500)


@authenticate_session
async def resume_container(request: Request) -> JSONResponse:
    '''
    Authentication required. Resume a HIBERNATED container: recreate its pod from the saved snapshot
    image (falls back to the base image if it was never saved), reconstructing the create request
    from the stored row. The surviving/new Service routes to it via the app=<name> label.
    '''
    container_id = None
    try:
        request_data: dict = await request.json()
        container_id = request_data['container_id']
        logger.info("resume requested", extra={"container_id": container_id})

        ops = ContainerOps(DB_CONFIG)
        row_result = await asyncio.to_thread(ops.find_one, filters={"id": container_id})
        row: dict = row_result.data
        if not row:
            logger.warning("resume: container not found", extra={"container_id": container_id})
            return JSONResponse(content={'error': f'Container {container_id} not found'}, status_code=404)

        # mark RESUMING so the UI can show progress
        await asyncio.to_thread(ops.update, filters={"id": container_id}, data={"status": ContainerStatus.RESUMING, "last_request_id": request_id_var.get()})

        # No DB credentials in the user pod (same as create): status is written by the central
        # status_monitor, not an in-pod sidecar. CONTAINER_ID rides only so container-maker can stamp
        # the browseterm/container-id label. Keep any stored env vars.
        environment_variables: dict = {
            **(row.get('environment_vars') or {}),
            'CONTAINER_ID': container_id,
        }
        resource_limits = ResourceLimits(
            cpu_limit=row.get('cpu_limit') or '1',
            memory_limit=row.get('memory_limit') or '1Gi',
            storage_limit=row.get('storage_limit') or '2Gi',
            snapshot_size_limit='2Gi',
        )
        k8s_request = CreateContainerK8SRequest(
            image_id=row['image_id'],
            container_name=row['name'],
            network_name=f"{row['user_id']}-namespace",
            exposure_level=2,
            publish_information=row.get('port_mappings') or [],
            environment_variables=environment_variables,
            resource_limits=resource_limits,
        )
        container_service = ContainerService()
        # recreate the pod FROM the snapshot (saved_image); base image if it was never saved.
        response = await container_service.create_container_in_k8s(
            k8s_request, image_name_override=row.get('saved_image')
        )
        # sync the new pod identity back to the row so the next save resolves it; RUNNING (the
        # central status_monitor keeps the status accurate thereafter). ip_address MUST be updated
        # here: resume creates a brand-new Service with a new ClusterIP, and the monitor only touches
        # status — without this the terminal keeps dialing the old (deleted) IP and SSH times out.
        await asyncio.to_thread(
            ops.update,
            filters={"id": container_id},
            data={
                "kubernetes_id": response.container_id,
                "ip_address": response.container_ip,
                "associated_resources": response.associated_resources,
                "status": ContainerStatus.RUNNING,
                "last_request_id": request_id_var.get(),
            },
        )
        logger.info("resume complete", extra={"container_id": container_id, "kubernetes_id": response.container_id})
        return JSONResponse(
            content={'status': 'resumed', 'container_id': container_id, 'kubernetes_id': response.container_id},
            status_code=200,
        )
    except HTTPException as e:
        return JSONResponse(content={'error': e.detail}, status_code=e.status_code)
    except Exception as e:
        logger.error("resume failed", extra={"container_id": container_id}, exc_info=True)
        if container_id:
            try:
                await asyncio.to_thread(
                    ContainerOps(DB_CONFIG).update,
                    filters={"id": container_id}, data={"status": ContainerStatus.FAILED},
                )
            except Exception:
                pass
        return JSONResponse(content={'error': f"Error resuming container: {str(e)}"}, status_code=500)


@authenticate_session
async def container_activity(request: Request) -> JSONResponse:
    '''
    Authenticated activity heartbeat, called by the terminal page while a terminal is in use.
    Does two things from one call:
      1. Refreshes the login session TTL — via the @authenticate_session decorator, so a user
         working only in a terminal (WebSocket traffic, no other HTTP requests) is NOT logged out.
      2. Stamps last_active_at on the container — the idle signal the reaper reads to decide what
         to hibernate. Scoped to the caller's own container (id + user_id).
    '''
    try:
        request_data: dict = await request.json()
        container_id = request_data.get('container_id')
        if not container_id:
            return JSONResponse(content={'error': 'container_id is required'}, status_code=400)
        user_info = request.state.user_info
        user_id = user_info.id if hasattr(user_info, 'id') else user_info['id']
        ops = ContainerOps(DB_CONFIG)
        await asyncio.to_thread(
            ops.update,
            filters={"id": container_id, "user_id": user_id},
            data={"last_active_at": datetime.now(timezone.utc)},
        )
        return JSONResponse(content={'status': 'ok'}, status_code=200)
    except Exception as e:
        return JSONResponse(content={'error': f"Error recording activity: {str(e)}"}, status_code=500)


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
