'''
Image database operations.
'''

# builtins
from typing import Any, Dict, Optional, List
import asyncio

# modules
from browseterm_db.operations import OperationResult
from browseterm_db.operations.all_operations import ImageOps
from src.common.config import DB_CONFIG

# DTOs
from src.db_ops.dto.image_dto import GetImageDataModel


async def get_image(filters: GetImageDataModel) -> Optional[Dict[str, Any]]:
    '''
    Get a single image from the database using provided filters.

    Args:
        filters: GetImageDataModel with one or more of: id, name, image

    Returns:
        Dict with image data if found, otherwise None

    Raises:
        Exception: If database operation fails
        ValueError: If validation fails
    '''
    try:
        image_ops: ImageOps = ImageOps(DB_CONFIG)

        # Build filters dict with only provided fields
        query_filters: Dict[str, Any] = {}
        if filters.id:
            query_filters['id'] = filters.id
        if filters.name:
            query_filters['name'] = filters.name
        if filters.image:
            query_filters['image'] = filters.image

        result: OperationResult = await asyncio.to_thread(image_ops.find_one, query_filters)
        if result.error:
            raise Exception(result.error)
        return result.data
    except ValueError:
        # re-raise explicit validation errors
        raise
    except Exception as e:
        print(f"Error getting image: {e}")
        raise Exception(f"Database operation failed: {str(e)}")


async def list_all_existing_images() -> List[Dict[str, Any]]:
    '''
    List all existing images in the database.
    Returns:
        List of image dictionaries (can be empty if none exist)
    Raises:
        Exception: If database operation fails
    '''
    try:
        image_ops: ImageOps = ImageOps(DB_CONFIG)
        # Empty filter returns all (subject to implementation)
        result: OperationResult = await asyncio.to_thread(image_ops.find, filters={"is_active": True})
        if result.error:
            raise Exception(result.error)
        return result.data or []
    except Exception as e:
        print(f"Error listing images: {e}")
        raise Exception(f"Database operation failed: {str(e)}")
