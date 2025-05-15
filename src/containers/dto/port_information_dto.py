from pydantic import BaseModel
from typing import Optional


class PortInformationModel(BaseModel):
    name: Optional[str] = None  # name of the port
    container_port: int  # port of the container
    protocol: Optional[str] = None  # protocol of the port
