# modules
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub

# GRPC Types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# utils
from src.common.utils import read_certs

# config
from src.common.config import CONTAINER_MAKER_CA_ENV_VAR
from src.common.config import CONTAINER_MAKER_CERT_ENV_VAR
from src.common.config import CONTAINER_MAKER_KEY_ENV_VAR
from src.common.config import CONTAINER_MAKER_CA_FILE
from src.common.config import CONTAINER_MAKER_CERT_FILE
from src.common.config import CONTAINER_MAKER_KEY_FILE
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT

# grpc utils
from src.common.grpc_utils import GRPCUtils

# third party
import grpc

# data models
from src.containers.data_transformers.create_container_transformer import CreateContainerInputDataTransformer
from src.containers.data_transformers.create_container_transformer import CreateContainerOutputDataTransformer
from src.data_models.containers import ContainerResponseModel
from src.data_models.containers import CreateContainerModel


class ContainerMakerClient:
    '''
    A client for the ContainerMaker API.
    '''
    def __init__(self) -> None:
        '''
        Initialize the ContainerMakerClient.
        '''
        # read certificates
        self.client_key: bytes = read_certs(CONTAINER_MAKER_KEY_ENV_VAR, CONTAINER_MAKER_KEY_FILE)
        self.client_cert: bytes = read_certs(CONTAINER_MAKER_CERT_ENV_VAR, CONTAINER_MAKER_CERT_FILE)
        self.ca_cert: bytes = read_certs(CONTAINER_MAKER_CA_ENV_VAR, CONTAINER_MAKER_CA_FILE)

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

    def create_container(self, create_container_data: CreateContainerModel) -> ContainerResponseModel:
        '''
        Create a container.
        '''
        try:
            breakpoint()
            # transform data
            create_container_request: CreateContainerRequest = CreateContainerInputDataTransformer.transform(create_container_data)
            # call the stub
            container_response: ContainerResponse = self.stub.createContainer(create_container_request)
            # transform data
            container_response_model: ContainerResponseModel = CreateContainerOutputDataTransformer.transform(container_response)
            # return the response
            return container_response_model
        except Exception as e:
            raise e

