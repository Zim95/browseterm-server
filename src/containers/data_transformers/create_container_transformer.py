# modules
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer

# grpc
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PublishInformation as GRPCPublishInformation
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel

# pydantic BaseModel(s)
from src.containers.dto.create_container_dto import CreateContainerModel
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.port_information_dto import PortInformationModel


class CreateContainerInputDataTransformer(InputDataTransformer):
    '''
    Transform the input data for the CreateContainer RPC.
    BaseModel -> GRPC
    '''
    @classmethod
    def transform(cls, input_data: CreateContainerModel) -> CreateContainerRequest:
        exposure_level_map: dict = {
            1: GRPCExposureLevel.EXPOSURE_LEVEL_INTERNAL,
            2: GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_LOCAL,
            3: GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_EXTERNAL,
            4: GRPCExposureLevel.EXPOSURE_LEVEL_EXPOSED
        }
        exposure_level: GRPCExposureLevel = exposure_level_map.get(input_data.exposure_level.value, GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_LOCAL)
        publish_information: list[GRPCPublishInformation] = [
            GRPCPublishInformation(
                publish_port=publish_info.publish_port,
                target_port=publish_info.target_port,
                protocol=publish_info.protocol,
                node_port=publish_info.node_port
            )
            for publish_info in input_data.publish_information
        ]
        return CreateContainerRequest(
            image_name=input_data.image_name,
            container_name=input_data.container_name,
            network_name=input_data.network_name,
            exposure_level=exposure_level,
            publish_information=publish_information,
            environment_variables=input_data.environment_variables
        )


class CreateContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the CreateContainer RPC.
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
                    protocol=port.protocol,
                ) for port in output_data.ports
            ],
        )
