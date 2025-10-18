# builtins
from unittest import TestCase
from typing import Dict, Any

# local
from src.authentication.data_transformers.google_user_info_transformer import GoogleUserInfoTransformer
from src.authentication.dto.user_info_dto import UserInfoModel
from browseterm_db.models.users import AuthProvider


class TestGoogleUserInfoTransformer(TestCase):
    '''
    Test the GoogleUserInfoTransformer.
    Tests transformation from Google API response to UserInfoModel.
    '''

    def setUp(self) -> None:
        '''
        Setup test data for Google API responses.
        '''
        # Successful Google API response
        self.google_api_response_success: Dict[str, Any] = {
            'id': '123456789',
            'name': 'John Doe',
            'email': 'john.doe@gmail.com',
            'picture': 'https://example.com/photo.jpg'
        }

        # Google API response with missing optional fields
        self.google_api_response_minimal: Dict[str, Any] = {
            'id': '987654321',
            'name': None,
            'email': None,
            'picture': None
        }

    def test_transform_google_response_to_user_info_model_success(self) -> None:
        '''
        Test successful transformation of complete Google API response.
        '''
        # Transform
        user_info: UserInfoModel = GoogleUserInfoTransformer.transform(self.google_api_response_success)

        # Assert
        self.assertEqual(user_info.provider_id, '123456789')
        self.assertEqual(user_info.name, 'John Doe')
        self.assertEqual(user_info.email, 'john.doe@gmail.com')
        self.assertEqual(user_info.profile_picture_url, 'https://example.com/photo.jpg')
        self.assertEqual(user_info.provider, AuthProvider.GOOGLE)
    
    def test_transform_google_response_with_minimal_data(self) -> None:
        '''
        Test transformation of Google API response with minimal data.
        '''
        # Transform
        user_info: UserInfoModel = GoogleUserInfoTransformer.transform(self.google_api_response_minimal)

        # Assert
        self.assertEqual(user_info.provider_id, '987654321')
        self.assertIsNone(user_info.name)
        self.assertIsNone(user_info.email)
        self.assertIsNone(user_info.profile_picture_url)
        self.assertEqual(user_info.provider, AuthProvider.GOOGLE)
    
    def test_transform_google_response_with_string_id(self) -> None:
        '''
        Test that Google ID is converted to string properly.
        '''
        google_response: Dict[str, Any] = {
            'id': 'string_id_123',
            'name': 'Test User',
            'email': 'test@gmail.com',
            'picture': None
        }

        user_info: UserInfoModel = GoogleUserInfoTransformer.transform(google_response)

        self.assertIsInstance(user_info.provider_id, str)
        self.assertEqual(user_info.provider_id, 'string_id_123')
