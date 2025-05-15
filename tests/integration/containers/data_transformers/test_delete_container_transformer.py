from unittest import TestCase

# grpc types
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse

# data transformers
from src.containers.data_transformers.delete_container_transformer import DeleteContainerInputDataTransformer
from src.containers.data_transformers.delete_container_transformer import DeleteContainerOutputDataTransformer

# dto
from src.containers.dto.delete_container_dto import DeleteContainerDataModel
from src.containers.dto.delete_container_response_dto import DeleteContainerResponseModel


class TestDeleteContainerTransformer(TestCase):
    def setUp(self) -> None:
        self.delete_container_input_data: DeleteContainerDataModel = DeleteContainerDataModel(
            container_id='1',
            network_name='test-network'
        )
        self.delete_container_output_data: DeleteContainerResponse = DeleteContainerResponse(
            container_id='1',
            status='Deleted'
        )

    def test_transform_delete_container_data_model_to_delete_container_request(self) -> None:
        # transform
        delete_container_request: DeleteContainerRequest = DeleteContainerInputDataTransformer.transform(
            self.delete_container_input_data)
        # assert
        self.assertEqual(delete_container_request.container_id, self.delete_container_input_data.container_id)
        self.assertEqual(delete_container_request.network_name, self.delete_container_input_data.network_name)

    def test_transform_delete_container_response_to_delete_container_response_model(self) -> None:
        # transform
        delete_container_response_model: DeleteContainerResponseModel = DeleteContainerOutputDataTransformer.transform(
            self.delete_container_output_data)
        # assert
        self.assertEqual(delete_container_response_model.container_id, self.delete_container_output_data.container_id)
        self.assertEqual(delete_container_response_model.status, self.delete_container_output_data.status)
