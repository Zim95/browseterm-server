# grpc types
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse

# data transformers
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer

# dto
from src.containers.dto.delete_container_dto import DeleteContainerDataModel
from src.containers.dto.delete_container_response_dto import DeleteContainerResponseModel


class DeleteContainerInputDataTransformer(InputDataTransformer):
    '''
    Transform the input data for the DeleteContainer RPC.
    '''
    @classmethod
    def transform(cls, input_data: DeleteContainerDataModel) -> DeleteContainerRequest:
        return DeleteContainerRequest(container_id=input_data.container_id, network_name=input_data.network_name)


class DeleteContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the DeleteContainer RPC.
    '''
    @classmethod
    def transform(cls, output_data: DeleteContainerResponse) -> DeleteContainerResponseModel:
        return DeleteContainerResponseModel(container_id=output_data.container_id, status=output_data.status)
