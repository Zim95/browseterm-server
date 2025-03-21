# builtins
from unittest import TestCase

# grpc
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel
from container_maker_spec.types_pb2 import PortInformation as GRPCPortInformation

# pydantic BaseModel(s)
from src.data_models.containers import CreateContainerModel
from src.data_models.containers import ExposureLevel as BaseModelExposureLevel

# data transformer
from src.containers.data_transformers.create_container_transformer import CreateContainerInputDataTransformer
from src.containers.data_transformers.create_container_transformer import CreateContainerOutputDataTransformer

class TestCreateContainerTransformer(TestCase):
    '''
    Test the CreateContainerTransformer.
    '''
    def setUp(self) -> None:
        # setup for input data
        self.container_name: str = 'test-container'
        self.network_name: str = 'test-namespace'
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.exposure_level = BaseModelExposureLevel.EXPOSED
        self.publish_information = [
            {'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'},
            {'publish_port': 2224, 'target_port': 22, 'protocol': 'TCP', 'node_port': 3000},
        ]
        self.environment_variables: dict[str, str] = {
            'SSH_PASSWORD': '12345678',
            'SSH_USERNAME': 'test-user',
        }

        # input data: Pydantic BaseModel
        # to be transformed to GRPC CreateContainerRequest
        self.input_data: CreateContainerModel = CreateContainerModel(
            image_name=self.image_name,
            container_name=self.container_name,
            network_name=self.network_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )

        # setup for output data
        self.container_id: str = 'test-container-id'
        self.container_ip: str = '127.0.0.1'
        self.container_network: str = 'test-container-network'
        self.container_ports: list[GRPCPortInformation] = [
            GRPCPortInformation(name='test-port-name-1', container_port=2222, protocol='TCP'),
            GRPCPortInformation(name='test-port-name-2', container_port=2224, protocol='TCP'),
        ]
        # output_data: GRPC ContainerResponse Message
        # to be transformed to ContainerResponseModel
        self.output_data: ContainerResponse = ContainerResponse(
            container_id=self.container_id,
            container_name=self.container_name,
            container_ip=self.container_ip,
            container_network=self.container_network,
            ports=self.container_ports
        )

    def test_transform_create_container_model_to_create_container_request(self) -> None:
        # transform
        output_data: CreateContainerRequest = CreateContainerInputDataTransformer.transform(self.input_data)

        # assert
        self.assertEqual(output_data.container_name, self.container_name)
        self.assertEqual(output_data.image_name, self.image_name)
        self.assertEqual(output_data.network_name, self.network_name)
        self.assertEqual(output_data.exposure_level, GRPCExposureLevel.EXPOSURE_LEVEL_EXPOSED)

        # first publish information
        self.assertEqual(output_data.publish_information[0].publish_port, 2222)
        self.assertEqual(output_data.publish_information[0].target_port, 22)
        self.assertEqual(output_data.publish_information[0].protocol, 'TCP')
        self.assertEqual(output_data.publish_information[0].node_port, 0)  # this is default integer value in GRPC messages.
        # In container-maker, we set the value of Node port to None if it is 0.

        # second publish information
        self.assertEqual(output_data.publish_information[1].publish_port, 2224)
        self.assertEqual(output_data.publish_information[1].target_port, 22)
        self.assertEqual(output_data.publish_information[1].protocol, 'TCP')
        self.assertEqual(output_data.publish_information[1].node_port, 3000)

        # environment variable
        self.assertEqual(output_data.environment_variables, self.environment_variables)

        # should work for empty environment variables too.
        emtpy_env_input_data: CreateContainerModel = CreateContainerModel(
            image_name=self.image_name,
            container_name=self.container_name,
            network_name=self.network_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
        )
        output_data_empty_env: CreateContainerRequest = CreateContainerInputDataTransformer.transform(emtpy_env_input_data)
        self.assertEqual(output_data_empty_env.environment_variables, {})

    def test_transform_create_container_request_to_create_container_model(self) -> None:
        # transform
        output_data: CreateContainerModel = CreateContainerOutputDataTransformer.transform(self.output_data)

        # assert
        self.assertEqual(output_data.container_name, self.container_name)
        self.assertEqual(output_data.container_id, self.container_id)
        self.assertEqual(output_data.container_ip, self.container_ip)
        self.assertEqual(output_data.container_network, self.container_network)

        # check ports
        self.assertEqual(output_data.container_ports[0].name, self.container_ports[0].name)
        self.assertEqual(output_data.container_ports[0].container_port, self.container_ports[0].container_port)
        self.assertEqual(output_data.container_ports[0].protocol, self.container_ports[0].protocol)
        self.assertEqual(output_data.container_ports[1].name, self.container_ports[1].name)
        self.assertEqual(output_data.container_ports[1].container_port, self.container_ports[1].container_port)
        self.assertEqual(output_data.container_ports[1].protocol, self.container_ports[1].protocol)
