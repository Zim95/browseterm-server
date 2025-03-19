# modules
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from src.common.utils import read_certs

from src.common.config import CONTAINER_MAKER_CA_ENV_VAR
from src.common.config import CONTAINER_MAKER_CERT_ENV_VAR
from src.common.config import CONTAINER_MAKER_KEY_ENV_VAR
from src.common.config import CONTAINER_MAKER_CA_FILE
from src.common.config import CONTAINER_MAKER_CERT_FILE
from src.common.config import CONTAINER_MAKER_KEY_FILE
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT

from src.common.grpc_utils import GRPCUtils

# third party
import grpc


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
