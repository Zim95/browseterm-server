from enum import Enum


class ExposureLevel(int, Enum):
    INTERNAL: int = 1  # only pod
    CLUSTER_LOCAL: int = 2  # service with cluster ip
    CLUSTER_EXTERNAL: int = 3  # service with external ip
    EXPOSED: int = 4  # ingress level
