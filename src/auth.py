'''
Authentication and authorization.
Authentication currently supported are: Github, Google.
Authorization is done by checking permissions.
'''

from functools import wraps


def authenticate_session(func: callable) -> callable:
    @wraps(func)
    async def wrapper(*args: tuple, **kwargs: dict) -> any:
        '''
        Authenticate the request.
        '''
        # TODO: Implement authentication.
        # For now, just return the request data.
        return await func(*args, **kwargs)
    return wrapper


def authorize_session(func: callable) -> callable:
    @wraps(func)
    async def wrapper(*args: tuple, **kwargs: dict) -> any:
        '''
        Authorize the request.
        '''
        return await func(*args, **kwargs)
    return wrapper