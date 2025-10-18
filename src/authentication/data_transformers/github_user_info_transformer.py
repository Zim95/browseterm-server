from typing import Dict, Any
from src.authentication.data_transformers import InputDataTransformer
from src.authentication.dto.user_info_dto import UserInfoModel
from browseterm_db.models.users import AuthProvider


class GithubUserInfoTransformer(InputDataTransformer):
    '''
    Transform GitHub API user info response to UserInfoModel
    '''
    @classmethod
    def transform(cls, input_data: Dict[str, Any]) -> UserInfoModel:
        '''
        Transform GitHub user info to standardized UserInfoModel
        Args:
            input_data: Raw response from GitHub User Info API
        Returns:
            UserInfoModel
        '''
        return UserInfoModel(
            provider_id=str(input_data.get('id')),
            name=input_data.get('name'),
            email=input_data.get('email'),
            profile_picture_url=input_data.get('avatar_url'),
            provider=AuthProvider.GITHUB
        )
