from pydantic import BaseModel


class LogoutResponseModel(BaseModel):
    '''
    Logout response model
    '''
    message: str
    success: bool
