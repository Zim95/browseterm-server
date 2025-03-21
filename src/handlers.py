'''
Route handlers.
Their job is to parse request data, call some class and return response data.
'''

from src.containers.containers import ContainerMakerClient
from src.data_models.echo import EchoRequestData, EchoResponseData
from src.data_models.containers import CreateContainerModel, ContainerResponseModel


async def echo(request: EchoRequestData) -> EchoResponseData:
    '''
    Simply echo the request message.
    '''
    return EchoResponseData(message=request.message)


async def create_container(request: CreateContainerModel) -> ContainerResponseModel:
    '''
    Create a container.
    '''
    try:
        # create a container maker client
        container_maker_client: ContainerMakerClient = ContainerMakerClient()
        # create a container
        container_response_model: ContainerResponseModel = container_maker_client.create_container(request)
        # return the response
        return container_response_model
    except Exception as e:
        raise e
