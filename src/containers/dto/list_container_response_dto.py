from pydantic import BaseModel
from typing import List
from src.containers.dto.container_response_dto import ContainerResponseModel


class ListContainerResponseModel(BaseModel):
    containers: List[ContainerResponseModel]  # list of containers
