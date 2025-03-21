from pydantic import BaseModel


class EchoRequestData(BaseModel):
    '''
    Echo request data
    '''
    message: str


class EchoResponseData(BaseModel):
    '''
    Echo response data
    '''
    message: str
