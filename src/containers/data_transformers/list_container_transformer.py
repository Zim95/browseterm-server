
# grpc types
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import ListContainerResponse

# dtos
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.list_container_dto import ListContainerDataModel
from src.containers.dto.list_container_response_dto import ListContainerResponseModel

# data transformers
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer
from src.containers.dto.port_information_dto import PortInformationModel


class ListContainerInputDataTransformer(InputDataTransformer):
    '''
    Transform the input data for the ListContainer RPC.
    '''
    @classmethod
    def transform(cls, input_data: ListContainerDataModel) -> ListContainerRequest:
        return ListContainerRequest(network_name=input_data.network_name)


class ListContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the ListContainer RPC.
    '''
    @classmethod
    def transform(cls, output_data: ListContainerResponse) -> ListContainerResponseModel:
        containers: list[ContainerResponseModel] = []
        for container in output_data.containers:
            containers.append(
                ContainerResponseModel(
                    container_id=container.container_id,
                    container_name=container.container_name,
                    container_ip=container.container_ip,
                    container_network=container.container_network,
                    container_ports=[
                        PortInformationModel(
                            name=port.name,
                            container_port=port.container_port,
                            protocol=port.protocol,
                        ) for port in container.ports
                    ],
                )
            )
        return ListContainerResponseModel(containers=containers)
