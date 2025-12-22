
from pydantic import BaseModel
from typing import List, Optional, Any
from src.containers.dto.port_information_dto import PortInformationModel


class ContainerResponseModel(BaseModel):
    container_name: str  # name of the container
    container_id: str  # id of the container
    container_ip: str  # ip of the container
    container_network: str  # network of the container
    container_ports: List[PortInformationModel]  # ports of the container
    associated_resources: Optional[Any] = None  # associated k8s resources
