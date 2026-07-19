# modules
from typing import Dict, Any, Optional
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIStub

# GRPC Types
from container_maker_spec.types_pb2 import CreateContainerRequest as GRPCCreateContainerRequest
from container_maker_spec.types_pb2 import GetContainerRequest as GRPCGetContainerRequest
from container_maker_spec.types_pb2 import ListContainerRequest as GRPCListContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest as GRPCDeleteContainerRequest 
from container_maker_spec.types_pb2 import ContainerResponse as GRPCContainerResponse
from container_maker_spec.types_pb2 import ListContainerResponse as GRPCListContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerResponse as GRPCDeleteContainerResponse
from container_maker_spec.types_pb2 import SaveContainerRequest as GRPCSaveContainerRequest

# utils
from src.common.exceptions import ContainerDBException, ContainerMakerException
from src.common.utils import ResourceUnitConverter
from src.containers.dto.publish_information_dto import PublishInformationModel
from src.db_ops.container_db_ops import create_container_in_db, get_container, update_container_in_db, list_user_containers as list_user_containers_db, delete_container as delete_container_db
from src.common.k8s_secrets import read_cert_from_k8s_secret

# config
from src.common.config import CONTAINER_MAKER_CERTS_SECRET_NAME, RESOURCE_CPU_REQUEST_RATIO, RESOURCE_EPHEMERAL_REQUEST_RATIO, RESOURCE_MEMORY_REQUEST_RATIO
from src.common.config import NAMESPACE
from src.common.config import CONTAINER_MAKER_HOST
from src.common.config import CONTAINER_MAKER_PORT

# grpc utils
from src.common.grpc_utils import GRPCUtils

# third party
import grpc
from fastapi import HTTPException

# data models
from src.containers.enum.exposure_level_enum import ExposureLevel
from src.data_models.containers import CreateContainerDBRequest, CreateContainerK8SRequest, GetContainerRequest, UpdateContainerRequest, ListUserContainersRequest, DeleteContainerDBRequest, DeleteContainerK8SRequest, SaveContainerK8SRequest
from src.db_ops.dto.container_dto import CreateContainerDBModel, GetContainerDBModel, UpdateContainerDBModel, UpdateContainerDBFilters, UpdateContainerDBData, ListContainersDBModel

# data transformers
from src.containers.data_transformers.list_container_transformer import ListContainerInputDataTransformer
from src.containers.data_transformers.list_container_transformer import ListContainerOutputDataTransformer
from src.containers.data_transformers.get_container_transformer import GetContainerInputDataTransformer
from src.containers.data_transformers.get_container_transformer import GetContainerOutputDataTransformer
from src.containers.data_transformers.create_container_transformer import CreateContainerInputDataTransformer
from src.containers.data_transformers.create_container_transformer import CreateContainerOutputDataTransformer
from src.containers.data_transformers.delete_container_transformer import DeleteContainerInputDataTransformer
from src.containers.data_transformers.delete_container_transformer import DeleteContainerOutputDataTransformer

# dtos
from src.containers.dto.create_container_dto import CreateContainerModel, ResourceRequirementsModel
from src.containers.dto.container_response_dto import ContainerResponseModel
from src.containers.dto.list_container_dto import ListContainerDataModel
from src.containers.dto.list_container_response_dto import ListContainerResponseModel
from src.containers.dto.get_container_dto import GetContainerDataModel
from src.containers.dto.delete_container_dto import DeleteContainerDataModel
from src.containers.dto.delete_container_response_dto import DeleteContainerResponseModel

# helpers
from src.containers.containers_helpers import is_user_within_container_limit, sanitize_container_name

# builtins
import asyncio

from src.db_ops.dto.image_dto import GetImageDataModel
from src.db_ops.image_db_ops import get_image


class ContainerService:
    '''
    A service for the ContainerMaker API.
    '''
    def __init__(self) -> None:
        '''
        Initialize the ContainerService.
        '''
        # read certificates directly from Kubernetes secrets
        self.client_key: bytes = read_cert_from_k8s_secret(
            CONTAINER_MAKER_CERTS_SECRET_NAME,
            NAMESPACE,
            'client.key'
        )
        self.client_cert: bytes = read_cert_from_k8s_secret(
            CONTAINER_MAKER_CERTS_SECRET_NAME,
            NAMESPACE,
            'client.crt'
        )
        self.ca_cert: bytes = read_cert_from_k8s_secret(
            CONTAINER_MAKER_CERTS_SECRET_NAME,
            NAMESPACE,
            'ca.crt'
        )

        # create GRPC channel and stub
        self.grpc_utils: GRPCUtils = GRPCUtils(
            host=CONTAINER_MAKER_HOST,
            port=CONTAINER_MAKER_PORT,
            stub_class=ContainerMakerAPIStub,
            secure=True,
            client_key=self.client_key,
            client_cert=self.client_cert,
            ca_cert=self.ca_cert
        )
        self.channel: grpc.Channel = self.grpc_utils.channel
        self.stub: ContainerMakerAPIStub = self.grpc_utils.stub

    async def get_container_info(self, get_container_request: GetContainerRequest) -> ContainerResponseModel:
        '''
        Get container information by container ID from db.
        '''
        try:
            get_container_model: GetContainerDBModel = GetContainerDBModel(
                container_id=get_container_request.container_id,
                user_id=get_container_request.user_id
            )
            return await get_container(get_container_model)
        except ContainerMakerException as e:
            raise HTTPException(status_code=500, detail=f"Error getting container info from ContainerMaker: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting container info: {str(e)}")

    async def create_container_in_db(self, create_container_db_request: CreateContainerDBRequest) -> dict:
        '''
        Create a Container in DB.
        '''
        try:
            # check if the user is within the container limit
            is_within_limit: Dict = await is_user_within_container_limit(create_container_db_request.user_id)
            if not is_within_limit['is_within_limit']:
                raise Exception(
                    f"Maximum number of containers reached. "
                    f"You can have up to {is_within_limit['current_subscription_plan_max_containers']} containers. "
                    f"You have {is_within_limit['number_of_containers']} containers."
                )

            create_container_db_model: CreateContainerDBModel = CreateContainerDBModel(
                user_id=create_container_db_request.user_id,
                image_id=create_container_db_request.image_id,
                name=create_container_db_request.container_name,
                cpu_limit=create_container_db_request.cpu_limit,
                memory_limit=create_container_db_request.memory_limit,
                storage_limit=create_container_db_request.storage_limit,
                port_mappings=create_container_db_request.publish_information,
                environment_variables=create_container_db_request.environment_variables  # Fixed: was environment_vars
            )
            create_container_db_result: dict = await create_container_in_db(create_container_db_model)
            print("create_container_db_result: ", create_container_db_result)
            return create_container_db_result
        except ContainerDBException as e:
            raise HTTPException(status_code=500, detail=f"Error creating container in database: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating container: {str(e)}")

    async def create_container_in_k8s(self, create_container_k8s_request: CreateContainerK8SRequest) -> ContainerResponseModel:
        '''
        Create container in k8s.
        This is the actual container creation logic.
        NOTE: Here, we need to create different containers, eg: SSH Container, Web Socket Container.
              Therefore, we will not check for limits here.
        '''
        image: Optional[Dict[str, Any]] = await get_image(GetImageDataModel(id=create_container_k8s_request.image_id))
        if not image:
            raise Exception(f"Image with id {create_container_k8s_request.image_id} not found")
        try:
            resource_req_model: ResourceRequirementsModel = ResourceRequirementsModel(
                cpu_request=ResourceUnitConverter.derive_cpu_request(create_container_k8s_request.resource_limits.cpu_limit, RESOURCE_CPU_REQUEST_RATIO),
                cpu_limit=create_container_k8s_request.resource_limits.cpu_limit,
                memory_request=ResourceUnitConverter.derive_memory_request(create_container_k8s_request.resource_limits.memory_limit, RESOURCE_MEMORY_REQUEST_RATIO),
                memory_limit=create_container_k8s_request.resource_limits.memory_limit,
                ephemeral_request=ResourceUnitConverter.derive_memory_request(create_container_k8s_request.resource_limits.storage_limit, RESOURCE_EPHEMERAL_REQUEST_RATIO),
                ephemeral_limit=create_container_k8s_request.resource_limits.storage_limit,
                snapshot_size_limit=create_container_k8s_request.resource_limits.snapshot_size_limit
            )
            create_container_k8s_model: CreateContainerModel = CreateContainerModel(
                image_name=image['image'],
                container_name=sanitize_container_name(create_container_k8s_request.container_name),
                network_name=create_container_k8s_request.network_name,
                exposure_level=ExposureLevel(create_container_k8s_request.exposure_level),
                publish_information=[
                    PublishInformationModel(
                        publish_port=p.get('publish_port', 2222),
                        target_port=p.get('target_port', 22),
                        protocol=p.get('protocol', 'TCP'),
                        node_port=p.get('node_port')
                    )
                    for p in create_container_k8s_request.publish_information
                ],
                environment_variables=create_container_k8s_request.environment_variables,
                resource_requirements=resource_req_model
            )
            grpc_create_container_request: GRPCCreateContainerRequest = CreateContainerInputDataTransformer.transform(create_container_k8s_model)
            # call the stub: Turn it into an async thread.
            grpc_container_response = await asyncio.to_thread(self.stub.createContainer, grpc_create_container_request)
            # format the container name
            # Remove suffix (pod/service/ingress) and timestamp from container name
            # Format: mycontainer-pod-1706565890 → mycontainer
            # Format: mycontainer-service → mycontainer
            parts = grpc_container_response.container_name.split('-')
            if len(parts) >= 2 and parts[-1].isdigit():  # Has timestamp (e.g., pod-1706565890)
                # Remove both suffix and timestamp: mycontainer-pod-1706565890 → mycontainer
                grpc_container_response.container_name = '-'.join(parts[:-2])
            elif len(parts) >= 1 and parts[-1] in ['pod', 'service', 'ingress']:  # No timestamp
                # Remove just suffix: mycontainer-service → mycontainer
                grpc_container_response.container_name = '-'.join(parts[:-1])
            # transform data
            return CreateContainerOutputDataTransformer.transform(grpc_container_response)
        except ContainerMakerException as e:
            raise HTTPException(status_code=500, detail=f"Error creating container in ContainerMaker: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating container: {str(e)}")

    async def update_container(self, update_container_request: UpdateContainerRequest) -> dict:
        '''
        Update a container in the database.
        '''
        try:
            # Build filters
            filters = UpdateContainerDBFilters(
                id=update_container_request.filters.container_id,
                user_id=update_container_request.filters.user_id,
                kubernetes_id=update_container_request.filters.kubernetes_id,
                name=update_container_request.filters.name
            )

            # Build update data
            data = UpdateContainerDBData(
                image_id=update_container_request.data.image_id,
                name=update_container_request.data.name,
                status=update_container_request.data.status,
                cpu_limit=update_container_request.data.cpu_limit,
                memory_limit=update_container_request.data.memory_limit,
                storage_limit=update_container_request.data.storage_limit,
                ip_address=update_container_request.data.ip_address,
                port_mappings=update_container_request.data.port_mappings,
                environment_vars=update_container_request.data.environment_vars,
                associated_resources=update_container_request.data.associated_resources,
                kubernetes_id=update_container_request.data.kubernetes_id,
                saved_image=update_container_request.data.saved_image
            )

            # Create the DB model
            update_container_db_model = UpdateContainerDBModel(
                filters=filters,
                data=data
            )

            # Update in database
            result = await update_container_in_db(update_container_db_model)
            # update_container_in_db returns None on success (no data from DB update operation)
            return result or {'success': True, 'message': 'Container updated successfully'}
        except ContainerDBException as e:
            raise HTTPException(status_code=500, detail=f"Error updating container in database: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating container: {str(e)}")

    async def list_user_containers(self, list_containers_request: ListUserContainersRequest) -> list:
        '''
        List all containers for a user.
        '''
        try:
            list_containers_db_model = ListContainersDBModel(
                user_id=list_containers_request.user_id,
                limit=list_containers_request.limit,
                offset=list_containers_request.offset
            )
            containers = await list_user_containers_db(
                list_containers_db_model.user_id,
                limit=list_containers_db_model.limit,
                offset=list_containers_db_model.offset
            )
            return containers or []
        except ContainerDBException as e:
            raise HTTPException(status_code=500, detail=f"Error listing containers: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing containers: {str(e)}")

    async def delete_container_in_db(self, delete_container_db_request: DeleteContainerDBRequest) -> dict:
        '''
        Delete a container from the database.
        '''
        try:
            result = await delete_container_db(
                container_id=delete_container_db_request.container_id,
                user_id=delete_container_db_request.user_id
            )
            return {'success': result, 'container_id': delete_container_db_request.container_id}
        except ContainerDBException as e:
            raise HTTPException(status_code=500, detail=f"Error deleting container from database: {str(e)}")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting container: {str(e)}")

    async def delete_container_in_k8s(self, delete_container_k8s_request: DeleteContainerK8SRequest) -> DeleteContainerResponseModel:
        '''
        Delete a container from Kubernetes.
        '''
        try:
            delete_container_k8s_model = DeleteContainerDataModel(
                container_id=delete_container_k8s_request.container_id,
                network_name=delete_container_k8s_request.network_name
            )
            grpc_delete_container_request: GRPCDeleteContainerRequest = DeleteContainerInputDataTransformer.transform(delete_container_k8s_model)
            grpc_delete_response = await asyncio.to_thread(self.stub.deleteContainer, grpc_delete_container_request)
            return DeleteContainerOutputDataTransformer.transform(grpc_delete_response)
        except ContainerMakerException as e:
            raise HTTPException(status_code=500, detail=f"Error deleting container in ContainerMaker: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting container: {str(e)}")

    async def save_container_in_k8s(self, save_container_k8s_request: SaveContainerK8SRequest):
        '''
        Trigger a container snapshot/save via container-maker.
        NOTE: container-maker blocks until the snapshot Job completes, so callers should run
        this in the background. Save progress is delivered via the DB save_status trigger -> SSE,
        not this return value.
        '''
        try:
            grpc_save_container_request = GRPCSaveContainerRequest(
                container_id=save_container_k8s_request.container_id,
                network_name=save_container_k8s_request.network_name
            )
            grpc_save_response = await asyncio.to_thread(self.stub.saveContainer, grpc_save_container_request)
            return grpc_save_response
        except ContainerMakerException as e:
            raise HTTPException(status_code=500, detail=f"Error saving container in ContainerMaker: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving container: {str(e)}")

