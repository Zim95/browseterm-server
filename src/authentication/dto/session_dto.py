from pydantic import BaseModel
from typing import Optional, Dict, Any


class SessionDataModel(BaseModel):
    '''
    Session data model
    '''
    user_info: Dict[str, Any]
    subscription_info: Dict[str, Any]
    current_subscription_plan: Dict[str, Any]


class SessionResponseModel(BaseModel):
    '''
    Session response model
    '''
    session_id: str
    user_info: Dict[str, Any]
    subscription_info: Dict[str, Any]
    current_subscription_plan: Dict[str, Any]


class SessionValidationModel(BaseModel):
    '''
    Session validation result model
    '''
    is_valid: bool
    session_data: Optional[SessionDataModel] = None
    ttl: Optional[int] = None
