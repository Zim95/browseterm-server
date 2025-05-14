import time

# kubernetes
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# common
from src.common.config import CERT_MANAGER_CRON_JOB_NAME
from src.common.config import CERT_MANAGER_CRON_JOB_NAMESPACE


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
