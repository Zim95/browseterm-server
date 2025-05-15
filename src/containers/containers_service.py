# modules
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub

# GRPC Types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# utils
from src.common.utils import read_cert_from_env_var

# config
from src.common.config import CONTAINER_MAKER_CLIENT_CERT_ENV_VAR
from src.common.config import CONTAINER_MAKER_CLIENT_KEY_ENV_VAR
from src.common.config import CONTAINER_MAKER_CA_ENV_VAR
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT

# grpc utils
from src.common.grpc_utils import GRPCUtils

# third party
import grpc

# data transformers
from src.containers.data_transformers.create_container_transformer import CreateContainerInputDataTransformer
from src.containers.data_transformers.create_container_transformer import CreateContainerOutputDataTransformer

# dtos
from src.containers.dto.create_container_dto import CreateContainerModel
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.list_container_dto import ListContainerDataModel
from src.containers.dto.list_container_response_dto import ListContainerResponseModel
from src.containers.dto.get_container_dto import GetContainerDataModel
from src.containers.dto.delete_container_dto import DeleteContainerDataModel
from src.containers.dto.delete_container_response_dto import DeleteContainerResponseModel


# builtins
import asyncio


class ContainerMakerClient:
    '''
    A client for the ContainerMaker API.
    '''
    def __init__(self) -> None:
        '''
        Initialize the ContainerMakerClient.
        '''
        # read certificates
        self.client_key: bytes = read_cert_from_env_var(CONTAINER_MAKER_CLIENT_KEY_ENV_VAR)
        self.client_cert: bytes = read_cert_from_env_var(CONTAINER_MAKER_CLIENT_CERT_ENV_VAR)
        self.ca_cert: bytes = read_cert_from_env_var(CONTAINER_MAKER_CA_ENV_VAR)

        # create GRPC channel and stub
        self.grpc_utils: GRPCUtils = GRPCUtils(
            host=CONTAINER_MAKER_HOST,
            port=CONTAINER_MAKER_PORT,
            stub_class=ContainerMakerAPIStub,
            secure=True,
            client_key=self.client_key,
            client_cert=self.client_cert,
            ca_cert=self.ca_cert
        )
        self.channel: grpc.Channel = self.grpc_utils.channel
        self.stub: ContainerMakerAPIStub = self.grpc_utils.stub

    async def create_container(self, create_container_data: CreateContainerModel) -> ContainerResponseModel:
        '''
        Create an SSH container and a Socket-SSH container.
        '''
        try:
            # transform data
            create_container_request: CreateContainerRequest = CreateContainerInputDataTransformer.transform(create_container_data)
            # call the stub: Turn it into an async thread.
            container_response: ContainerResponse = await asyncio.to_thread(self.stub.createContainer, create_container_request)
            container_response.container_name = '-'.join(container_response.container_name.split('-')[:-1])  # remove the suffix like: service, ingress or pod
            # transform data
            container_response_model: ContainerResponseModel = CreateContainerOutputDataTransformer.transform(container_response)
            # return the response
            return container_response_model
        except Exception as e:
            raise e


    async def list_container(self, list_container_data: ListContainerDataModel) -> ListContainerResponseModel:
        '''
        List a container.
        '''
        pass

    async def get_container(self, get_container_data: GetContainerDataModel) -> ContainerResponseModel:
        '''
        Get a container.
        '''
        pass
    
    async def delete_container(self, delete_container_data: DeleteContainerDataModel) -> DeleteContainerResponseModel:
        '''
        Delete a container.
        '''
        pass
