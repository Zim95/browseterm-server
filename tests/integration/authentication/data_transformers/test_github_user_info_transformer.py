# builtins
from unittest import TestCase
from typing import Dict, Any, Optional

# local
from src.authentication.data_transformers.github_user_info_transformer import GithubUserInfoTransformer
from src.authentication.dto.user_info_dto import UserInfoModel
from browseterm_db.models.users import AuthProvider


class TestGithubUserInfoTransformer(TestCase):
    '''
    Test the GithubUserInfoTransformer.
    Tests transformation from GitHub API response to UserInfoModel.
    '''

    def setUp(self) -> None:
        '''
        Setup test data for GitHub API responses.
        '''
        # Successful GitHub API response
        self.github_api_response_success: Dict[str, Any] = {
            'id': 123456,
            'name': 'Jane Smith',
            'email': 'jane.smith@github.com',
            'avatar_url': 'https://avatars.githubusercontent.com/u/123456'
        }

        # GitHub API response with missing optional fields
        self.github_api_response_minimal: Dict[str, Any] = {
            'id': 654321,
            'name': None,
            'email': None,
            'avatar_url': None
        }

    def test_transform_github_response_to_user_info_model_success(self) -> None:
        '''
        Test successful transformation of complete GitHub API response.
        '''
        # Transform
        user_info: UserInfoModel = GithubUserInfoTransformer.transform(self.github_api_response_success)

        # Assert
        self.assertEqual(user_info.provider_id, '123456')
        self.assertEqual(user_info.name, 'Jane Smith')
        self.assertEqual(user_info.email, 'jane.smith@github.com')
        self.assertEqual(user_info.profile_picture_url, 'https://avatars.githubusercontent.com/u/123456')
        self.assertEqual(user_info.provider, AuthProvider.GITHUB)

    def test_transform_github_response_with_minimal_data(self) -> None:
        '''
        Test transformation of GitHub API response with minimal data.
        '''
        # Transform
        user_info: UserInfoModel = GithubUserInfoTransformer.transform(self.github_api_response_minimal)

        # Assert
        self.assertEqual(user_info.provider_id, '654321')
        self.assertIsNone(user_info.name)
        self.assertIsNone(user_info.email)
        self.assertIsNone(user_info.profile_picture_url)
        self.assertEqual(user_info.provider, AuthProvider.GITHUB)

    def test_transform_github_response_integer_id_to_string(self) -> None:
        '''
        Test that GitHub integer ID is converted to string.
        '''
        github_response: Dict[str, Any] = {
            'id': 999999,
            'name': 'Test User',
            'email': 'test@github.com',
            'avatar_url': None
        }
        user_info: UserInfoModel = GithubUserInfoTransformer.transform(github_response)

        self.assertIsInstance(user_info.provider_id, str)
        self.assertEqual(user_info.provider_id, '999999')
