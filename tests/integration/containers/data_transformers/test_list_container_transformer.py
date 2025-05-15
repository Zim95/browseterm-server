from unittest import TestCase

# dto
from src.containers.dto.list_container_dto import ListContainerDataModel
from src.containers.dto.list_container_response_dto import ListContainerResponseModel

# grpc types
from container_maker_spec.types_pb2 import ListContainerResponse
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation as GRPCPortInformation


# data transformers
from src.containers.data_transformers.list_container_transformer import ListContainerInputDataTransformer
from src.containers.data_transformers.list_container_transformer import ListContainerOutputDataTransformer


class TestListContainerTransformer(TestCase):

    def setUp(self) -> None:
        # list conrtainer input data
        self.list_container_input_data: ListContainerDataModel = ListContainerDataModel(network_name='test-network')

        # list container response grpc
        self.list_container_response: ListContainerResponse = ListContainerResponse(
            containers=[
                ContainerResponse(
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
            ]
        )
        # list container response with empty ports
        self.list_container_response_empty_ports: ListContainerResponse = ListContainerResponse(
            containers=[
                ContainerResponse(
                    container_id='1',
                    container_name='test-container',
                    container_ip='127.0.0.1',
                    container_network='test-network'
                )
            ]
        )

    def test_transform_list_container_data_model_to_list_container_request(self) -> None:
        # transform
        list_container_request: ListContainerRequest = ListContainerInputDataTransformer.transform(
            self.list_container_input_data)
        # assert
        self.assertEqual(list_container_request.network_name, self.list_container_input_data.network_name)

    def test_transform_list_container_response_to_list_container_response_model(self) -> None:
        # transform
        list_container_response_model: ListContainerResponseModel = ListContainerOutputDataTransformer.transform(
            self.list_container_response)
        # assert
        self.assertEqual(list_container_response_model.containers[0].container_id, self.list_container_response.containers[0].container_id)
        self.assertEqual(list_container_response_model.containers[0].container_name, self.list_container_response.containers[0].container_name)
        self.assertEqual(list_container_response_model.containers[0].container_ip, self.list_container_response.containers[0].container_ip)
        self.assertEqual(list_container_response_model.containers[0].container_network, self.list_container_response.containers[0].container_network)
        self.assertEqual(list_container_response_model.containers[0].container_ports[0].name, self.list_container_response.containers[0].ports[0].name)
        self.assertEqual(list_container_response_model.containers[0].container_ports[0].container_port, self.list_container_response.containers[0].ports[0].container_port)
        self.assertEqual(list_container_response_model.containers[0].container_ports[0].protocol, self.list_container_response.containers[0].ports[0].protocol)

        # now test with empty port
        list_container_response_model: ListContainerResponseModel = ListContainerOutputDataTransformer.transform(
            self.list_container_response_empty_ports)
        self.assertEqual(list_container_response_model.containers[0].container_ports, [])  # empty list
