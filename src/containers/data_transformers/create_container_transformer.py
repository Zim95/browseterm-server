# modules
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer

# third party
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse


class CreateContainerInputDataTransformer(InputDataTransformer):
    '''
    Transform the input data for the CreateContainer RPC.
    '''
    @classmethod
    def transform(cls, input_data: CreateContainerDataClass) -> CreateContainerRequest:
        pass


class CreateContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the CreateContainer RPC.
    '''
    @classmethod
    def transform(cls, output_data: ContainerResponse) -> CreateContainerDataClass:
        pass