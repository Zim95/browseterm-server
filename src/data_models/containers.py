from pydantic import BaseModel
from enum import Enum
from typing import List, Dict, Optional


class PublishInformationModel(BaseModel):
    publish_port: int  # the port of the service
    target_port: int  # the port of the pod
    protocol: str  # the protocol of the service
    node_port: Optional[int] = None  # the node port of the service


class ExposureLevel(int, Enum):
    INTERNAL: int = 1  # only pod
    CLUSTER_LOCAL: int = 2  # service with cluster ip
    CLUSTER_EXTERNAL: int = 3  # service with external ip
    EXPOSED: int = 4  # ingress level


class CreateContainerModel(BaseModel):
    image_name: str  # name of the image to use
    container_name: str  # name of the container
    network_name: str  # name of the network
    exposure_level: ExposureLevel  # exposure level of the container
    publish_information: List[PublishInformationModel]  # list of publish information
    environment_variables: Optional[Dict[str, str]] = {} # environment variables


class PortInformationModel(BaseModel):
    name: Optional[str] = None  # name of the port
    container_port: int  # port of the container
    protocol: Optional[str] = None  # protocol of the port


class ContainerResponseModel(BaseModel):
    container_name: str  # name of the container
    container_id: str  # id of the container
    container_ip: str  # ip of the container
    container_network: str  # network of the container
    container_ports: List[PortInformationModel]  # ports of the container
