from pydantic import BaseModel
from typing import Dict, Any


class LoginResponseModel(BaseModel):
    '''
    Login response model
    '''
    session_id: str
    user_info: Dict[str, Any]
    subscription_info: Dict[str, Any]
    current_subscription_plan: Dict[str, Any]
