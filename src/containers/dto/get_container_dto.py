from pydantic import BaseModel


class GetContainerDataModel(BaseModel):
    container_id: str  # id of the container
    network_name: str  # name of the network
