from pydantic import BaseModel


class DeleteContainerResponseModel(BaseModel):
    container_id: str  # id of the container
    status: str  # status of the container
