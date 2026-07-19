# builtins
from unittest import TestCase

# pydantic
from pydantic import ValidationError

# data models
from src.data_models.containers import SaveContainerK8SRequest


class TestSaveContainerK8SRequest(TestCase):
    '''
    Validate the SaveContainerK8SRequest data model used by the save flow.
    '''
    def test_valid_save_container_request(self) -> None:
        '''
        A valid payload with container_id and network_name should validate
        and expose those fields.
        '''
        save_request: SaveContainerK8SRequest = SaveContainerK8SRequest(
            container_id='container-123',
            network_name='test-network'
        )
        self.assertEqual(save_request.container_id, 'container-123')
        self.assertEqual(save_request.network_name, 'test-network')

    def test_save_container_request_from_dict(self) -> None:
        '''
        The model should validate when constructed from a raw dict
        (mirrors how the api handler builds it from JSON).
        '''
        save_request: SaveContainerK8SRequest = SaveContainerK8SRequest(
            **{'container_id': 'abc', 'network_name': 'net'}
        )
        self.assertEqual(save_request.container_id, 'abc')
        self.assertEqual(save_request.network_name, 'net')

    def test_missing_fields_raise_validation_error(self) -> None:
        '''
        Both container_id and network_name are required.
        '''
        with self.assertRaises(ValidationError):
            SaveContainerK8SRequest(container_id='only-id')
        with self.assertRaises(ValidationError):
            SaveContainerK8SRequest(network_name='only-net')
