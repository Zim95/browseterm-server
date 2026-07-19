from pydantic import BaseModel
from typing import Optional, Any


class ResourceLimits(BaseModel):
    cpu_limit: str
    memory_limit: str
    storage_limit: str
    snapshot_size_limit: str


class CreateContainerDBRequest(BaseModel):
    user_id: str
    image_id: str
    container_name: str
    cpu_limit: str
    memory_limit: str
    storage_limit: str
    publish_information: list[dict]
    environment_variables: Optional[dict[str, Any]]


class CreateContainerK8SRequest(BaseModel):
    image_id: str
    container_name: str
    network_name: str
    exposure_level: int
    publish_information: list[dict]
    environment_variables: Optional[dict[str, Any]]
    resource_limits: Optional[ResourceLimits]


class UpdateContainerFilters(BaseModel):
    """Filters to identify which container(s) to update."""
    container_id: Optional[str] = None
    user_id: Optional[str] = None
    kubernetes_id: Optional[str] = None
    name: Optional[str] = None


class UpdateContainerData(BaseModel):
    """Fields that can be updated on a container."""
    image_id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    storage_limit: Optional[str] = None
    ip_address: Optional[str] = None
    port_mappings: Optional[list[dict]] = None
    environment_vars: Optional[dict[str, Any]] = None
    associated_resources: Optional[list[dict[str, Any]]] = None
    kubernetes_id: Optional[str] = None
    saved_image: Optional[str] = None


class UpdateContainerRequest(BaseModel):
    """Request model for updating a container."""
    filters: UpdateContainerFilters
    data: UpdateContainerData


class GetContainerRequest(BaseModel):
    """Request model for getting a container."""
    container_id: str
    user_id: str


class ListUserContainersRequest(BaseModel):
    """Request model for listing user containers."""
    user_id: str
    limit: Optional[int] = None
    offset: Optional[int] = None


class DeleteContainerDBRequest(BaseModel):
    """Request model for deleting a container from the database."""
    container_id: str
    user_id: str


class DeleteContainerK8SRequest(BaseModel):
    """Request model for deleting a container from Kubernetes."""
    container_id: str
    network_name: str


class SaveContainerK8SRequest(BaseModel):
    """Request model for saving (snapshotting) a container in Kubernetes."""
    container_id: str
    network_name: str
