
from pydantic import BaseModel
from typing import List, Dict, Optional
from src.containers.enum.exposure_level_enum import ExposureLevel
from src.containers.dto.publish_information_dto import PublishInformationModel


class ResourceRequirementsModel(BaseModel):
    """Resource requirements for container creation in Kubernetes."""
    cpu_request: str = '100m'
    cpu_limit: str = '1'
    memory_request: str = '256Mi'
    memory_limit: str = '1Gi'
    ephemeral_request: str = '512Mi'
    ephemeral_limit: str = '2Gi'
    snapshot_size_limit: str = '2Gi'


class CreateContainerModel(BaseModel):
    image_name: str  # name of the image to use
    container_name: str  # name of the container
    network_name: str  # name of the network
    exposure_level: ExposureLevel  # exposure level of the container
    publish_information: List[PublishInformationModel]  # list of publish information
    environment_variables: Optional[Dict[str, str]] = {}  # environment variables
    resource_requirements: Optional[ResourceRequirementsModel] = None  # resource requirements
