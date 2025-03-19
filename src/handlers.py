'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

from src.dataclasses.echo import EchoRequestData, EchoResponseData


async def echo(request: EchoRequestData) -> EchoResponseData:
    '''
    Simply echo the request message.
    '''
    return EchoResponseData(message=request.message)
