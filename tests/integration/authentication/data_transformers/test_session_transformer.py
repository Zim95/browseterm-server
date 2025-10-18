# builtins
from unittest import TestCase
from typing import Dict, Any, Optional

# local
from src.authentication.data_transformers.session_transformer import (
    SessionInputTransformer,
    SessionOutputTransformer,
    SessionResponseTransformer
)
from src.authentication.dto.session_dto import SessionDataModel, SessionResponseModel


class TestSessionTransformers(TestCase):
    '''
    Test the Session Transformers.
    Tests transformation of session data between different formats.
    '''

    def setUp(self) -> None:
        '''
        Setup test data for session transformations.
        '''
        self.user_info: Dict[str, Any] = {
            'id': 1,
            'name': 'Test User',
            'email': 'test@example.com',
            'provider': 'google'
        }

        self.subscription_info: Dict[str, Any] = {
            'id': 10,
            'user_id': 1,
            'subscription_type_id': 1,
            'status': 'active'
        }

        self.current_subscription_plan: Dict[str, Any] = {
            'id': 1,
            'name': 'Free',
            'price': 0,
            'features': ['feature1', 'feature2']
        }

        self.session_data_dict: Dict[str, Any] = {
            'user_info': self.user_info,
            'subscription_info': self.subscription_info,
            'current_subscription_plan': self.current_subscription_plan
        }

        self.session_id: str = 'test-session-id-12345'

    def test_session_input_transformer(self) -> None:
        '''
        Test transformation from dict to SessionDataModel.
        '''
        # Transform
        session_data: SessionDataModel = SessionInputTransformer.transform(self.session_data_dict)

        # Assert
        self.assertEqual(session_data.user_info, self.user_info)
        self.assertEqual(session_data.subscription_info, self.subscription_info)
        self.assertEqual(session_data.current_subscription_plan, self.current_subscription_plan)
    
    def test_session_output_transformer(self) -> None:
        '''
        Test transformation from SessionDataModel to dict.
        '''
        # Create SessionDataModel
        session_data: SessionDataModel = SessionDataModel(
            user_info=self.user_info,
            subscription_info=self.subscription_info,
            current_subscription_plan=self.current_subscription_plan
        )

        # Transform
        output_dict: Dict[str, Any] = SessionOutputTransformer.transform(session_data)

        # Assert
        self.assertEqual(output_dict['user_info'], self.user_info)
        self.assertEqual(output_dict['subscription_info'], self.subscription_info)
        self.assertEqual(output_dict['current_subscription_plan'], self.current_subscription_plan)

    def test_session_response_transformer(self) -> None:
        '''
        Test transformation to SessionResponseModel.
        '''
        # Transform
        session_response: SessionResponseModel = SessionResponseTransformer.transform(
            self.session_id,
            self.session_data_dict
        )

        # Assert
        self.assertEqual(session_response.session_id, self.session_id)
        self.assertEqual(session_response.user_info, self.user_info)
        self.assertEqual(session_response.subscription_info, self.subscription_info)
        self.assertEqual(session_response.current_subscription_plan, self.current_subscription_plan)

    def test_session_input_transformer_with_empty_dicts(self) -> None:
        '''
        Test SessionInputTransformer with empty dictionaries.
        '''
        empty_data: Dict[str, Any] = {
            'user_info': {},
            'subscription_info': {},
            'current_subscription_plan': {}
        }

        session_data: SessionDataModel = SessionInputTransformer.transform(empty_data)

        self.assertEqual(session_data.user_info, {})
        self.assertEqual(session_data.subscription_info, {})
        self.assertEqual(session_data.current_subscription_plan, {})

    def test_round_trip_transformation(self) -> None:
        '''
        Test that data survives a round trip: dict -> SessionDataModel -> dict.
        '''
        # Transform to SessionDataModel
        session_data: SessionDataModel = SessionInputTransformer.transform(self.session_data_dict)

        # Transform back to dict
        output_dict: Dict[str, Any] = SessionOutputTransformer.transform(session_data)

        # Assert they are equal
        self.assertEqual(output_dict, self.session_data_dict)
