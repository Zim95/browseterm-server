from unittest import TestCase

# grpc types
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation as GRPCPortInformation
# data transformers
from src.containers.data_transformers.get_container_transformer import GetContainerInputDataTransformer
from src.containers.data_transformers.get_container_transformer import GetContainerOutputDataTransformer

# dto
from src.containers.dto.get_container_dto import GetContainerDataModel
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.port_information_dto import PortInformationModel


class TestGetContainerTransformer(TestCase):
    def setUp(self) -> None:
        self.get_container_input_data: GetContainerDataModel = GetContainerDataModel(
            container_id='1',
            network_name='test-network'
        )
        self.get_container_output_data: ContainerResponse = ContainerResponse(
            container_id='1',
            container_name='test-container',
            container_ip='127.0.0.1',
            container_network='test-network',
            ports=[
                GRPCPortInformation(
                    name='test-port',
                    container_port=8080,
                    protocol='TCP'
                )
            ]
        )
        self.get_container_output_data_empty_ports: ContainerResponse = ContainerResponse(
            container_id='1',
            container_name='test-container',
            container_ip='127.0.0.1',
            container_network='test-network'
        )

    def test_transform_get_container_data_model_to_get_container_request(self) -> None:
        # transform
        get_container_request: GetContainerRequest = GetContainerInputDataTransformer.transform(
            self.get_container_input_data)
        # assert
        self.assertEqual(get_container_request.container_id, self.get_container_input_data.container_id)
        self.assertEqual(get_container_request.network_name, self.get_container_input_data.network_name)

    def test_transform_container_response_to_container_response_model(self) -> None:
        # transform
        container_response_model: ContainerResponseModel = GetContainerOutputDataTransformer.transform(
            self.get_container_output_data)
        # assert
        self.assertEqual(container_response_model.container_id, self.get_container_output_data.container_id)
        self.assertEqual(container_response_model.container_name, self.get_container_output_data.container_name)
        self.assertEqual(container_response_model.container_ip, self.get_container_output_data.container_ip)
        self.assertEqual(container_response_model.container_network, self.get_container_output_data.container_network)
        self.assertEqual(container_response_model.container_ports[0].name, self.get_container_output_data.ports[0].name)
        self.assertEqual(container_response_model.container_ports[0].container_port, self.get_container_output_data.ports[0].container_port)
        self.assertEqual(container_response_model.container_ports[0].protocol, self.get_container_output_data.ports[0].protocol)

    def test_transform_container_response_empty_ports_to_container_response_model(self) -> None:
        # transform
        container_response_model: ContainerResponseModel = GetContainerOutputDataTransformer.transform(
            self.get_container_output_data_empty_ports)
        # assert
        self.assertEqual(container_response_model.container_id, self.get_container_output_data_empty_ports.container_id)
        self.assertEqual(container_response_model.container_name, self.get_container_output_data_empty_ports.container_name)
        self.assertEqual(container_response_model.container_ip, self.get_container_output_data_empty_ports.container_ip)
        self.assertEqual(container_response_model.container_network, self.get_container_output_data_empty_ports.container_network)
        self.assertEqual(container_response_model.container_ports, [])  # empty list
