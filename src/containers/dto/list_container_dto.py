from pydantic import BaseModel


class ListContainerDataModel(BaseModel):
    network_name: str  # name of the network
