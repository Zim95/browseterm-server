from typing import Dict, Any
from src.authentication.data_transformers import InputDataTransformer, OutputDataTransformer
from src.authentication.dto.session_dto import SessionDataModel, SessionResponseModel


class SessionInputTransformer(InputDataTransformer):
    '''
    Transform user info and subscription data to SessionDataModel
    '''
    @classmethod
    def transform(cls, input_data: Dict[str, Any]) -> SessionDataModel:
        '''
        Transform user and subscription info to SessionDataModel
        Args:
            input_data: Dict containing user_info, subscription_info, current_subscription_plan
        Returns:
            SessionDataModel
        '''
        return SessionDataModel(
            user_info=input_data.get('user_info', {}),
            subscription_info=input_data.get('subscription_info', {}),
            current_subscription_plan=input_data.get('current_subscription_plan', {})
        )


class SessionOutputTransformer(OutputDataTransformer):
    '''
    Transform SessionDataModel to response format
    '''
    @classmethod
    def transform(cls, output_data: SessionDataModel) -> Dict[str, Any]:
        '''
        Transform SessionDataModel to dict format
        Args:
            output_data: SessionDataModel
        Returns:
            Dict containing session data
        '''
        return {
            'user_info': output_data.user_info,
            'subscription_info': output_data.subscription_info,
            'current_subscription_plan': output_data.current_subscription_plan
        }


class SessionResponseTransformer:
    '''
    Transform session data and session ID to SessionResponseModel
    '''
    @classmethod
    def transform(cls, session_id: str, session_data: Dict[str, Any]) -> SessionResponseModel:
        '''
        Transform session data to SessionResponseModel
        Args:
            session_id: Session ID
            session_data: Session data dict
        Returns:
            SessionResponseModel
        '''
        return SessionResponseModel(
            session_id=session_id,
            user_info=session_data.get('user_info', {}),
            subscription_info=session_data.get('subscription_info', {}),
            current_subscription_plan=session_data.get('current_subscription_plan', {})
        )
