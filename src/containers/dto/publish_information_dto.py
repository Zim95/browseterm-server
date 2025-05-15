from pydantic import BaseModel
from typing import Optional


class PublishInformationModel(BaseModel):
    publish_port: int  # the port of the service
    target_port: int  # the port of the pod
    protocol: str  # the protocol of the service
    node_port: Optional[int] = None  # the node port of the service
