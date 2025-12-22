'''
Container database operation DTOs.
'''

from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class CreateContainerDBModel(BaseModel):
    user_id: str  # id of the user
    image_id: str  # id of the image
    name: str  # name of the container
    port_mappings: List[Dict]  # list of publish information
    environment_variables: Optional[Dict[str, str]] = {}  # environment variables
    cpu_limit: Optional[str] = '1'  # CPU limit (e.g., "1")
    memory_limit: Optional[str] = '1Gi'  # Memory limit (e.g., "1Gi")
    storage_limit: Optional[str] = '2Gi'  # Storage limit (e.g., "2Gi")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'image_id': self.image_id,
            'name': self.name,
            'port_mappings': self.port_mappings,
            'environment_vars': self.environment_variables,  # DB column is environment_vars
            'cpu_limit': self.cpu_limit,
            'memory_limit': self.memory_limit,
            'storage_limit': self.storage_limit
        }


class UpdateContainerDBFilters(BaseModel):
    """Filters to identify which container(s) to update in DB."""
    id: Optional[str] = None  # container_id maps to id in DB
    user_id: Optional[str] = None
    kubernetes_id: Optional[str] = None
    name: Optional[str] = None

    def to_filter_dict(self) -> Dict[str, Any]:
        """Return only non-None fields for filtering."""
        return self.model_dump(exclude_none=True)


class UpdateContainerDBData(BaseModel):
    """Data fields that can be updated on a container in DB."""
    image_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    storage_limit: Optional[str] = None
    ip_address: Optional[str] = None
    port_mappings: Optional[List[Dict]] = None
    environment_vars: Optional[Dict[str, Any]] = None
    associated_resources: Optional[List[Dict[str, Any]]] = None
    kubernetes_id: Optional[str] = None
    saved_image: Optional[str] = None

    def to_update_dict(self) -> Dict[str, Any]:
        """Return only non-None fields for update."""
        return self.model_dump(exclude_none=True)


class UpdateContainerDBModel(BaseModel):
    """Model for updating container in DB with filters and data."""
    filters: UpdateContainerDBFilters
    data: UpdateContainerDBData


class DeleteContainerDBModel(BaseModel):
    container_id: str  # id of the container
    user_id: str  # id of the user


class GetContainerDBModel(BaseModel):
    container_id: str  # id of the container
    user_id: str  # id of the user


class ListContainersDBModel(BaseModel):
    user_id: str  # id of the user
    limit: Optional[int] = None  # optional limit
    offset: Optional[int] = None  # optional offset for pagination
