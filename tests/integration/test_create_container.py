# builtins
from unittest import TestCase
# grpc
import grpc
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import ListContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub
# config
from src.common.config import CONTAINER_MAKER_CA_ENV_VAR
from src.common.config import CONTAINER_MAKER_CERT_ENV_VAR
from src.common.config import CONTAINER_MAKER_KEY_ENV_VAR
from src.common.config import CONTAINER_MAKER_CA_FILE
from src.common.config import CONTAINER_MAKER_CERT_FILE
from src.common.config import CONTAINER_MAKER_KEY_FILE
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT
# modules
from src.common.utils import read_certs
from src.common.grpc_utils import GRPCUtils


NAMESPACE_NAME: str = 'test-grpc-namespace'


class TestGRPCContainerStub(TestCase):
    '''
    Here we will test:
    1. The actual creation and removal of containers.
    2. The creation and removal of duplicate containers.
    3. Test SSH container creation and communication.
    4. Test Websocket container creation and communication.
    5. Communication from websocket to ssh and retreival of data.

    NOTE: This is the most important test, when it comes to functionality.
          We will write it very carefully.
    '''
    def setUp(self) -> None:
        '''
        Setup the input values for the container.
        Don't worry about testing different exposure levels.
        We will assume that if one exposure level works, the others will too.
        '''
        print('Test: setUp TestGRPCContainerStub')  
        # creating the channel and stub.
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

        # Common container input variables.      
        self.namespace_name: str = NAMESPACE_NAME

        # SSH Container input variables.
        self.ssh_container_name: str = 'test-ssh-container'
        self.ssh_image_name: str = 'zim95/ssh_ubuntu:latest'
        self.ssh_publish_information: list[dict] = [
            {'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'},
        ]
        self.ssh_environment_variables: dict[str, str] = {
            'SSH_PASSWORD': '12345678',
            'SSH_USERNAME': 'test-user',
        }
        # create the protobuf message for ssh container.
        self.ssh_grpc_create_container_request: CreateContainerRequest = CreateContainerRequest(
            container_name=self.ssh_container_name,
            network_name=self.namespace_name,
            image_name=self.ssh_image_name,
            exposure_level=GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_LOCAL,  # For SSH only cluster local exposure level.
            publish_information=self.ssh_publish_information,
            environment_variables=self.ssh_environment_variables,
        )

        # Websocket Container input variables.
        # NOTE: We will add this once the other tests are done.

    def test_a_creation_and_removal_of_containers(self) -> None:
        '''
        Here we will only test with the SSH container. Why?
        Because if one container creation is working, the other should too.
        If its not, then theres something wrong with that container image.

        Here we will test if the container is created and deleted.
        '''
        print('Test: test_a_creation_and_removal_of_containers')
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        '''
        1. We figured out that, listContainer returns an empty list when called from servicer because it actually returns a list.
        2. When called from stub, it returns a GRPC message, a grpc message when theres no items in the list returns an empty ListContainerResponse.
        '''
        self.assertEqual(list_container_response, ListContainerResponse())

        # create the container
        create_container_response: ContainerResponse = self.stub.createContainer(self.ssh_grpc_create_container_request)
        container_name: str = '-'.join(create_container_response.container_name.split('-')[:-1])
        self.assertEqual(container_name, self.ssh_container_name)
        self.assertEqual(create_container_response.container_network, self.namespace_name)
        self.assertEqual(create_container_response.ports[0].container_port, self.ssh_publish_information[0]['publish_port'])
        self.assertEqual(create_container_response.ports[0].protocol, self.ssh_publish_information[0]['protocol'])

        # list the container
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        self.assertEqual(len(list_container_response.containers), 1)

        # delete the container
        delete_container_request: DeleteContainerRequest = DeleteContainerRequest(
            container_id=create_container_response.container_id, network_name=self.namespace_name
        )
        delete_container_response: DeleteContainerResponse = self.stub.deleteContainer(delete_container_request)
        self.assertEqual(delete_container_response.status, 'Deleted')

        # list the container again
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        self.assertEqual(list_container_response, ListContainerResponse())

    def test_b_creation_and_removal_of_duplicate_containers(self) -> None:
        '''
        Here we will test if the container is created and deleted.
        Here also, we will use 
        '''
        print('Test: test_b_creation_and_removal_of_duplicate_containers')
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        '''
        1. We figured out that, listContainer returns an empty list when called from servicer because it actually returns a list.
        2. When called from stub, it returns a GRPC message, a grpc message when theres no items in the list returns an empty ListContainerResponse.
        '''
        self.assertEqual(list_container_response, ListContainerResponse())

        # create the container
        create_container_response_1: ContainerResponse = self.stub.createContainer(self.ssh_grpc_create_container_request)
        container_name_1: str = '-'.join(create_container_response_1.container_name.split('-')[:-1])
        self.assertEqual(container_name_1, self.ssh_container_name)
        self.assertEqual(create_container_response_1.container_network, self.namespace_name)
        self.assertEqual(create_container_response_1.ports[0].container_port, self.ssh_publish_information[0]['publish_port'])
        self.assertEqual(create_container_response_1.ports[0].protocol, self.ssh_publish_information[0]['protocol'])

        # create the container again
        create_container_response_2: ContainerResponse = self.stub.createContainer(self.ssh_grpc_create_container_request)
        container_name_2: str = '-'.join(create_container_response_2.container_name.split('-')[:-1])
        self.assertEqual(container_name_2, self.ssh_container_name)
        self.assertEqual(create_container_response_2.container_network, self.namespace_name)
        self.assertEqual(create_container_response_2.ports[0].container_port, self.ssh_publish_information[0]['publish_port'])
        self.assertEqual(create_container_response_2.ports[0].protocol, self.ssh_publish_information[0]['protocol'])

        # compare the containers
        self.assertEqual(create_container_response_1.container_id, create_container_response_2.container_id)

        # check the number of containers
        # list the container
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        self.assertEqual(len(list_container_response.containers), 1)

        # delete the container: Deleting 1 container is enough, since both should be the same container.
        delete_container_request: DeleteContainerRequest = DeleteContainerRequest(
            container_id=create_container_response_1.container_id, network_name=self.namespace_name
        )
        delete_container_response: DeleteContainerResponse = self.stub.deleteContainer(delete_container_request)
        self.assertEqual(delete_container_response.status, 'Deleted')

        # list the container again
        list_container_request: ListContainerRequest = ListContainerRequest(network_name=self.namespace_name)
        list_container_response = self.stub.listContainer(list_container_request)
        self.assertEqual(list_container_response, ListContainerResponse())
