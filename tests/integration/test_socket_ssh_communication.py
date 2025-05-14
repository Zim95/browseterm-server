'''
Here we will test socket communication between the websocket and ssh container.
They use secrets - The ssh certificates.

The secrets only exist in the browseterm-new namespace.
So, these tests will be in the browseterm-new namespace.

So, we isolated these tests away from test_create_container.py
test_create_container runs in its own namespace.
When it ends, the namespace is deleted.

We cannot do that for browseterm-new namespace.
So these tests are isolated from test_create_container.py
'''

from unittest import TestCase
import ssl
import websocket
import json
import tempfile
import os
import base64

# config
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT
from src.common.config import CONTAINER_MAKER_CLIENT_KEY_ENV_VAR
from src.common.config import CONTAINER_MAKER_CLIENT_CERT_ENV_VAR
from src.common.config import CONTAINER_MAKER_CA_ENV_VAR

# utils
from src.common.grpc_utils import GRPCUtils
from src.common.utils import read_cert_from_env_var

# grpc
import grpc
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel

from src.containers.certificate_utils import CertificateUtils


# namespace name
'''
Why do we need to be in browseterm-new namespace?
- Basically, the secrets are in the browseterm-new namespace.
- We need to be in the same namespace to use the secrets.
'''
NAMESPACE_NAME: str = 'browseterm-new'


class TestSocketCommunication(TestCase):
    '''
    Here we will test socket communication between the websocket and ssh container.
    They use secrets - The ssh certificates.

    The secrets only exist in the browseterm-new namespace.
    So, these tests will be in the browseterm-new namespace.
    '''
    def setUp(self) -> None:
        '''
        Our exposure level is cluster local. This will create the service and the pod.
        This will be constant for these tests.
        '''
        # creating the channel and stub.
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

        # Common container input variables.      
        self.namespace_name: str = NAMESPACE_NAME

        # SSH Container input variables.
        self.ssh_container_name: str = 'test-ssh-container'
        self.ssh_image_name: str = 'zim95/ssh_ubuntu:latest'
        self.ssh_publish_information: list[dict] = [
            {'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'},
        ]
        self.ssh_environment_variables: dict[str, str] = {
            'SSH_PASSWORD': 'test_user_password',
            'SSH_USERNAME': 'test_user',
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
        self.web_socket_container_name: str = 'test-socket-ssh'
        # before creating the websocket container, we also need to create certificates.
        print(f'Creating {self.web_socket_container_name} certificates...')
        service_name: str = f"{self.web_socket_container_name}-service"
        # for now, we only have one service in the list.
        CertificateUtils.create_certificate_job(services=','.join([service_name]))
        print(f'Done creating {self.web_socket_container_name} certificates...')
        self.cert_name: str = f"{service_name}-certs"
        self.web_socket_certificates: dict = CertificateUtils.read_certificate_from_secret(self.cert_name)
        self.web_socket_image_name: str = 'zim95/socket-ssh:latest'
        self.web_socket_publish_information: list[dict] = [
            {'publish_port': 8000, 'target_port': 8000, 'protocol': 'TCP'},
        ]
        self.namespace_name: str = NAMESPACE_NAME
        self.web_socket_environment_variables: dict[str, str] = {
            'SERVER_KEY': base64.b64decode(self.web_socket_certificates['server.key']).decode('utf-8'),
            'SERVER_CRT': base64.b64decode(self.web_socket_certificates['server.crt']).decode('utf-8'),
            'CLIENT_KEY': base64.b64decode(self.web_socket_certificates['client.key']).decode('utf-8'),
            'CLIENT_CRT': base64.b64decode(self.web_socket_certificates['client.crt']).decode('utf-8'),
            'CA_CRT': base64.b64decode(self.web_socket_certificates['ca.crt']).decode('utf-8'),
        }
        self.web_socket_grpc_create_container_request: CreateContainerRequest = CreateContainerRequest(
            container_name=self.web_socket_container_name,
            network_name=self.namespace_name,
            image_name=self.web_socket_image_name,
            exposure_level=GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_LOCAL,
            publish_information=self.web_socket_publish_information,
            environment_variables=self.web_socket_environment_variables,
        )
        self.web_socket_host: str = service_name
        self.web_socket_port: int = 8000

    def test_socket_ssh_communication(self) -> None:
        '''
        Here we will test socket communication between the websocket and ssh container.
        1. Create the ssh container, get the ip address.
        2. Create the websocket container. We have the host and port.
        3. Send a connect request to the websocket container.
        4. Send shell command to the websocket container.
        5. Validate the response.
        '''
        print('Test: test_socket_ssh_communication')
        # create the ssh container
        print('Creating SSH Container...')
        ssh_container: ContainerResponse = self.stub.createContainer(self.ssh_grpc_create_container_request)
        ssh_container_ip: str = ssh_container.container_ip
        # create the websocket container
        print('Creating Websocket Container...')
        websocket_container: ContainerResponse = self.stub.createContainer(self.web_socket_grpc_create_container_request)
        '''
        We need to write our certificates to a file temporarily.
        This is because sslopt requires a file path.
        Our secrets are basically bytes, so we need to write them to a file temporarily.
        '''
        # Initialize certificate paths
        client_cert_path: str | None = None
        client_key_path: str | None = None
        ca_cert_path: str | None = None

        try:
            print('Creating temporary files for certificates...')
            # Create temporary files for certificates
            with tempfile.NamedTemporaryFile(delete=False) as client_cert_filet, \
                 tempfile.NamedTemporaryFile(delete=False) as client_key_filet, \
                 tempfile.NamedTemporaryFile(delete=False) as ca_cert_filet:

                # Write certificate data to temporary files
                client_cert_filet.write(base64.b64decode(self.web_socket_certificates['client.crt']))
                client_key_filet.write(base64.b64decode(self.web_socket_certificates['client.key']))
                ca_cert_filet.write(base64.b64decode(self.web_socket_certificates['ca.crt']))

                # Get the file paths
                client_cert_path = client_cert_filet.name  # name gives us the path.
                client_key_path = client_key_filet.name  # name gives us the path.
                ca_cert_path = ca_cert_filet.name  # name gives us the path.

            print('Connecting to the websocket container...')
            # connect to the websocket container
            websocket_connection: websocket.WebSocketApp = websocket.create_connection(
                f'wss://{self.web_socket_host}:{self.web_socket_port}',
                sslopt={
                    'certfile': client_cert_path,
                    'keyfile': client_key_path,
                    'ca_certs': ca_cert_path,
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'ssl_version': ssl.PROTOCOL_TLS,
                }
            )
            print('Sending connect request to the websocket container...')
            websocket_connection.send(json.dumps(
                {
                    'type': 'sshConnect',
                    'data': {
                        'ssh_hash': 'test_hash_connect',
                        'ssh_host': ssh_container_ip,
                        'ssh_port': 2222,
                        'ssh_username': self.ssh_environment_variables['SSH_USERNAME'],
                        'ssh_password': self.ssh_environment_variables['SSH_PASSWORD']
                    }
                }
            ))
            print('Connected to the websocket container...')
            connection_response: str = websocket_connection.recv()
            self.assertEqual('*** SSH CONNECTION ESTABLISHED ***' in connection_response, True)

            # send a shell command to the websocket container.
            expected_response: str = '/home/test_user'
            shell_command_response: str = ''
            print('Sending shell command to the websocket container...')
            while expected_response not in shell_command_response:
                websocket_connection.send(json.dumps(
                    {
                        'type': 'sshSendData',
                        'data': {
                            'ssh_hash': 'test_hash_connect',
                            'ssh_command': 'pwd\n'  # do not forget to add newline. It will act as a delimiter.
                        }
                    }
                ))
                shell_command_response = websocket_connection.recv()
            print('Received shell command response from the websocket container:', shell_command_response)
            self.assertEqual(expected_response in shell_command_response, True)
        finally:
            print('Cleaning up temporary files if they were created...')
            # Clean up temporary files if they were created
            if client_cert_path and os.path.exists(client_cert_path):
                os.unlink(client_cert_path)
            if client_key_path and os.path.exists(client_key_path):
                os.unlink(client_key_path)
            if ca_cert_path and os.path.exists(ca_cert_path):
                os.unlink(ca_cert_path)
            # delete the containers.
            print('Deleting Containers...')
            delete_websocket_container_request: DeleteContainerRequest = DeleteContainerRequest(
                container_id=websocket_container.container_id, network_name=self.namespace_name
            )
            delete_websocket_container_response: DeleteContainerResponse = self.stub.deleteContainer(delete_websocket_container_request)
            self.assertEqual(delete_websocket_container_response.status, 'Deleted')

            delete_ssh_container_request: DeleteContainerRequest = DeleteContainerRequest(
                container_id=ssh_container.container_id, network_name=self.namespace_name
            )
            delete_ssh_container_response: DeleteContainerResponse = self.stub.deleteContainer(delete_ssh_container_request)
            self.assertEqual(delete_ssh_container_response.status, 'Deleted')
            # delete the secret
            print('Deleting secret...')
            CertificateUtils.delete_secret(self.cert_name)
