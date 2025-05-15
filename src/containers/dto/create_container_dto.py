
from pydantic import BaseModel
from typing import List, Dict, Optional
from src.containers.enum.exposure_level_enum import ExposureLevel
from src.containers.dto.publish_information_dto import PublishInformationModel


class CreateContainerModel(BaseModel):
    image_name: str  # name of the image to use
    container_name: str  # name of the container
    network_name: str  # name of the network
    exposure_level: ExposureLevel  # exposure level of the container
    publish_information: List[PublishInformationModel]  # list of publish information
    environment_variables: Optional[Dict[str, str]] = {} # environment variables
