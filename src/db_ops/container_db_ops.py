'''
Container database operations.
'''

# builtins
from typing import Dict, Any, Optional
import asyncio

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import ContainerOps
from src.common.config import DB_CONFIG
from src.common.exceptions import ContainerDBException

# DTOs
from src.db_ops.dto.container_dto import CreateContainerDBModel, UpdateContainerDBModel


async def create_container_in_db(container_info: CreateContainerDBModel) -> Optional[Dict[str, Any]]:
    '''
    Create a container in the database.
    Ensures that duplicate containers (same name + user_id) cannot be created.
    Different users can have containers with the same name, but not the same user.
    '''
    try:
        container_ops: ContainerOps = ContainerOps(DB_CONFIG)
        # Validate required fields
        if not container_info.name or not container_info.user_id:
            raise ValueError("Container name and user_id are required")
        # check if a container with the same name and user_id already exists
        filters: Dict[str, Any] = {
            'name': container_info.name,
            'user_id': container_info.user_id
        }
        existing_container: OperationResult = await asyncio.to_thread(container_ops.find_one, filters)
        if existing_container.error:
            raise Exception(existing_container.error)
        if existing_container.data:
            raise ContainerDBException(f"Container with name '{container_info.name}' already exists for this user.")
        # Create the container
        create_result: OperationResult = await asyncio.to_thread(container_ops.insert, container_info.to_dict())
        if create_result.error:
            raise ContainerDBException(create_result.error)
        return create_result.data
    except ContainerDBException as e:
        raise ContainerDBException(f"Database operation failed: {str(e)}")
    except Exception as e:
        raise ContainerDBException(f"Database operation failed: {str(e)}")


async def update_container_in_db(update_data: UpdateContainerDBModel) -> Optional[Dict[str, Any]]:
    '''
    Update a container in the database.
    Uses filters to identify which container(s) to update and data for the update values.
    '''
    try:
        container_ops: ContainerOps = ContainerOps(DB_CONFIG)
        filters: Dict[str, Any] = update_data.filters.to_filter_dict()
        update_dict: Dict[str, Any] = update_data.data.to_update_dict()

        if not filters:
            raise ValueError("At least one filter is required")
        if not update_dict:
            raise ValueError("No fields to update")

        update_result: OperationResult = await asyncio.to_thread(
            container_ops.update, filters, update_dict
        )
        if update_result.error:
            raise ContainerDBException(update_result.error)
        return update_result.data
    except ContainerDBException as e:
        raise ContainerDBException(f"Database operation failed: {str(e)}")
    except Exception as e:
        raise ContainerDBException(f"Database operation failed: {str(e)}")


async def delete_container(container_id: str, user_id: str) -> bool:
    '''
    Delete a container from the database.
    Ensures that only the owner can delete the container.
    
    Args:
        container_id: Container ID (UUID as string)
        user_id: User ID (UUID as string) - to verify ownership
    
    Returns:
        True if container was successfully deleted, False otherwise
    
    Raises:
        Exception: If database operation fails
        ValueError: If container not found or user doesn't own the container
    '''
    try:
        container_ops: ContainerOps = ContainerOps(DB_CONFIG)

        # First, verify that the container exists and belongs to the user
        filters: Dict[str, Any] = {
            'id': container_id,
            'user_id': user_id
        }

        container: OperationResult = await asyncio.to_thread(container_ops.find_one, filters)

        if container.error:
            raise Exception(container.error)

        if not container.data:
            raise ValueError(
                f"Container with ID '{container_id}' not found or you don't have permission to delete it."
            )

        # Delete the container (soft delete in browseterm_db)
        delete_result: OperationResult = await asyncio.to_thread(container_ops.delete, filters)

        if delete_result.error:
            raise Exception(delete_result.error)

        return delete_result.success

    except ValueError as e:
        print(f"Validation error deleting container: {e}")
        raise e
    except Exception as e:
        print(f"Error deleting container: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def get_container(container_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    '''
    Get a container from the database by ID.
    Ensures that only the owner can access the container.
    
    Args:
        container_id: Container ID (UUID as string)
        user_id: User ID (UUID as string) - to verify ownership
    
    Returns:
        Dict containing the container data if found, None otherwise
    
    Raises:
        Exception: If database operation fails
    '''
    try:
        container_ops: ContainerOps = ContainerOps(DB_CONFIG)
        filters: Dict[str, Any] = {
            'id': container_id,
            'user_id': user_id
        }
        container: OperationResult = await asyncio.to_thread(container_ops.find_one, filters)
        if container.error:
            raise Exception(container.error)
        return container.data
    except Exception as e:
        print(f"Error getting container: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def list_user_containers(user_id: str, limit: Optional[int] = None, offset: Optional[int] = None) -> Optional[list]:
    '''
    List all containers for a specific user.
    
    Args:
        user_id: User ID (UUID as string)
        limit: Maximum number of containers to return (optional)
        offset: Number of containers to skip (optional, for pagination)
    
    Returns:
        List of dictionaries containing container data
    
    Raises:
        Exception: If database operation fails
    '''
    try:
        container_ops: ContainerOps = ContainerOps(DB_CONFIG)
        filters: Dict[str, Any] = {
            'user_id': user_id
        }
        containers: OperationResult = await asyncio.to_thread(container_ops.find, filters, limit=limit, offset=offset)
        if containers.error:
            raise Exception(containers.error)
        return containers.data
    except Exception as e:
        print(f"Error listing containers: {e}")
        raise Exception(f"Database operation failed: {str(e)}")
