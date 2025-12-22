from ast import Dict
import time
from typing import Any
import re

# kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# common
from src.common.config import CERT_MANAGER_CRON_JOB_NAME
from src.common.config import CERT_MANAGER_CRON_JOB_NAMESPACE
from src.db_ops.container_db_ops import list_user_containers
from src.db_ops.subscription_db_ops import get_user_current_subscription_plan
from src.db_ops.dto.subscription_dto import GetUserSubscriptionPlanModel


class CertificateUtils:
    '''
    A utility class for create, read and delete certificates using secrets and jobs.
    '''
    config.load_incluster_config()
    batch_v1: client.BatchV1Api = client.BatchV1Api()
    core_v1: client.CoreV1Api = client.CoreV1Api()  # Add CoreV1Api for secrets

    @classmethod
    def poll_until_completeion(cls, created_job: client.V1Job) -> None:
        '''
        Poll until the job is complete.
        '''
        while True:
            job: client.V1Job = cls.batch_v1.read_namespaced_job(name=created_job.metadata.name, namespace=CERT_MANAGER_CRON_JOB_NAMESPACE)
            if job.status.succeeded:
                break
            time.sleep(4)


    @classmethod
    def create_certificate_job(cls, services: str) -> client.V1Job:
        """
        Create self signed certificates for services.
        We already have a cronjob that creates the certificates.
        This function creates a job from that cronjob. While also passing services as an env variable.
        :params:
            services: Comma separated string containing service names. Eg: socket-ssh-service,some-other-service
        :returns: The created V1Job object.
        """
        try:
            # Get the cronjob
            cronjob: client.V1CronJob = cls.batch_v1.read_namespaced_cron_job(
                name=CERT_MANAGER_CRON_JOB_NAME,
                namespace=CERT_MANAGER_CRON_JOB_NAMESPACE
            )
            # Create a copy of the job template spec
            job_spec: client.V1JobSpec = client.V1JobSpec(
                ttl_seconds_after_finished=300,  # job pod will be deleted after 5 minutes
                template=client.V1PodTemplateSpec(
                    spec=client.V1PodSpec(
                        containers=[]  # We'll fill this in
                    )
                )
            )
            # Copy the entire job template spec
            job_spec.template.spec = cronjob.spec.job_template.spec.template.spec
            # Get the first container
            container: client.V1Container = job_spec.template.spec.containers[0]
            # Create the SERVICES env var
            services_env: client.V1EnvVar = client.V1EnvVar(name="SERVICES", value=services)
            # Add to existing env vars if any
            if container.env:
                container.env.append(services_env)
            else:
                container.env = [services_env]

            # Prepare metadata
            metadata: client.V1ObjectMeta = client.V1ObjectMeta(
                namespace=CERT_MANAGER_CRON_JOB_NAMESPACE
            )
            metadata.generate_name = f"{CERT_MANAGER_CRON_JOB_NAME}-job"

            # Create job from modified spec
            job: client.V1Job = client.V1Job(
                metadata=metadata,
                spec=job_spec
            )

            # Create the job
            created_job: client.V1Job = cls.batch_v1.create_namespaced_job(
                namespace=CERT_MANAGER_CRON_JOB_NAMESPACE,
                body=job
            )

            print(f"Created job {created_job.metadata.name} from cronjob {CERT_MANAGER_CRON_JOB_NAME}")
            cls.poll_until_completeion(created_job)
            print(f"Job {created_job.metadata.name} completed.")
        except ApiException as e:
            print(f"Error creating job from cronjob: {e}")
            raise

    @classmethod
    def read_certificate_from_secret(cls, secret_name: str) -> dict:
        '''
        Read the certificate from the secret.
        If secret.data is empty, return an empty dict.
        Otherwise, return the secret.data.
        :params:
            secret_name: The name of the secret to read.
        :returns:
            A dictionary containing the secret data.
        '''
        try:
            secret: client.V1Secret = cls.core_v1.read_namespaced_secret(
                name=secret_name, namespace=CERT_MANAGER_CRON_JOB_NAMESPACE
            )
            if secret.data:
                return secret.data
            return {}
        except ApiException as e:
            print(f"Error reading secret: {e}")
            raise

    @classmethod
    def delete_secret(cls, secret_name: str) -> None:
        '''
        Read secret, if it exists, delete the secret.
        :params:
            secret_name: The name of the secret to delete.
        :returns:
            None
        '''
        try:
            secret: client.V1Secret = cls.core_v1.read_namespaced_secret(
                name=secret_name, namespace=CERT_MANAGER_CRON_JOB_NAMESPACE
            )
            if secret:
                cls.core_v1.delete_namespaced_secret(name=secret_name, namespace=CERT_MANAGER_CRON_JOB_NAMESPACE)
        except ApiException as e:
            print(f"Error deleting secret: {e}")
            raise


async def is_user_within_container_limit(user_id: str) -> Dict:
    '''
    Check if the user is within the container limit.
    Args:
        user_id: User ID
    Returns:
        Dict containing the container limit information
    Raises:
        Exception: If database operation fails
    '''
    try:
        # get the current subscription plan of the user and get the max containers a user can have.
        current_subscription_plan: Dict[str, Any] = await get_user_current_subscription_plan(GetUserSubscriptionPlanModel(user_id=user_id))
        current_subscription_plan_max_containers: int = current_subscription_plan['max_containers']
        # get the number of containers the user has
        number_of_containers: int = len(await list_user_containers(user_id))
        # return True if the user is within the container limit, False otherwise
        return {
            'is_within_limit': number_of_containers < current_subscription_plan_max_containers,
            'number_of_containers': number_of_containers,
            'current_subscription_plan_max_containers': current_subscription_plan_max_containers
        }
    except Exception as e:
        print(f"Error checking user container limit: {e}")
        raise Exception(f"Error checking user container limit: {str(e)}")


def sanitize_container_name(container_name: str) -> str:
    '''
    Sanitize the container name for Kubernetes compatibility.
    - Convert to lowercase
    - Replace spaces and underscores with hyphens
    - Remove special characters (keep only alphanumeric and hyphens)
    
    Args:
        container_name: Container name
        
    Returns:
        Sanitized container name safe for Kubernetes
        
    Raises:
        Exception: If container name is invalid
    '''
    try:
        if not container_name or not isinstance(container_name, str):
            raise Exception("Container name is invalid")
        # Convert to lowercase and trim whitespace
        lowered: str = container_name.strip().lower()        
        # Replace spaces and underscores with hyphens
        hyphenated: str = lowered.replace(' ', '-').replace('_', '-')
        # Remove special characters (keep only alphanumeric and hyphens)
        sanitized: str = re.sub(r'[^a-z0-9-]', '', hyphenated)
        # Ensure it starts and ends with alphanumeric characters
        sanitized = re.sub(r'^-+|-+$', '', sanitized)  # Remove leading/trailing hyphens
        if not sanitized:
            sanitized = 'container'  # Fallback if name becomes empty
        return sanitized
    except Exception as e:
        print(f"Error sanitizing container name: {e}")
        raise Exception(f"Error sanitizing container name: {str(e)}")
