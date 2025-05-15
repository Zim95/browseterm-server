
# grpc types
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# dto
from src.containers.dto.get_container_dto import GetContainerDataModel
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.port_information_dto import PortInformationModel
# data transformers
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer


class GetContainerInputDataTransformer(InputDataTransformer):
    '''
    Transform the input data for the GetContainer RPC.
    '''
    @classmethod
    def transform(cls, input_data: GetContainerDataModel) -> GetContainerRequest:
        return GetContainerRequest(container_id=input_data.container_id, network_name=input_data.network_name)


class GetContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the GetContainer RPC.
    '''
    @classmethod
    def transform(cls, output_data: ContainerResponse) -> ContainerResponseModel:
        return ContainerResponseModel(
            container_id=output_data.container_id,
            container_name=output_data.container_name,
            container_ip=output_data.container_ip,
            container_network=output_data.container_network,
            container_ports=[
                PortInformationModel(
                    name=port.name,
                    container_port=port.container_port,
                    protocol=port.protocol) for port in output_data.ports
            ]
        )
