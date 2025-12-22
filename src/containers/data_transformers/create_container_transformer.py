# modules
from src.containers.data_transformers import InputDataTransformer
from src.containers.data_transformers import OutputDataTransformer

# grpc
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PublishInformation as GRPCPublishInformation
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel
from container_maker_spec.types_pb2 import ResourceRequirements as GRPCResourceRequirements

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

        # Build resource requirements if provided
        resource_requirements = None
        if input_data.resource_requirements:
            resource_requirements = GRPCResourceRequirements(
                cpu_request=input_data.resource_requirements.cpu_request,
                cpu_limit=input_data.resource_requirements.cpu_limit,
                memory_request=input_data.resource_requirements.memory_request,
                memory_limit=input_data.resource_requirements.memory_limit,
                ephemeral_request=input_data.resource_requirements.ephemeral_request,
                ephemeral_limit=input_data.resource_requirements.ephemeral_limit,
                snapshot_size_limit=input_data.resource_requirements.snapshot_size_limit
            )

        return CreateContainerRequest(
            image_name=input_data.image_name,
            container_name=input_data.container_name,
            network_name=input_data.network_name,
            exposure_level=exposure_level,
            publish_information=publish_information,
            environment_variables=input_data.environment_variables,
            resource_requirements=resource_requirements
        )


class CreateContainerOutputDataTransformer(OutputDataTransformer):
    '''
    Transform the output data for the CreateContainer RPC.
    '''
    @classmethod
    def _parse_associated_resources(cls, res):
        '''Parse associated resources recursively.'''
        result = {
            'resource_name': res.resource_name,
            'resource_type': res.resource_type
        }
        if res.container_resources:
            result['container_resources'] = {
                'cpu_request': res.container_resources.cpu_request,
                'cpu_limit': res.container_resources.cpu_limit,
                'memory_request': res.container_resources.memory_request,
                'memory_limit': res.container_resources.memory_limit,
                'ephemeral_request': res.container_resources.ephemeral_request,
                'ephemeral_limit': res.container_resources.ephemeral_limit,
                'snapshot_size_limit': res.container_resources.snapshot_size_limit
            }
        if res.associated_resources:
            result['associated_resources'] = [cls._parse_associated_resources(r) for r in res.associated_resources]
        return result

    @classmethod
    def transform(cls, output_data: ContainerResponse) -> ContainerResponseModel:
        # Parse associated resources if present (it's a repeated field/list)
        associated_resources = None
        if output_data.associated_resources:
            associated_resources = [cls._parse_associated_resources(r) for r in output_data.associated_resources]

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
            associated_resources=associated_resources,
        )
