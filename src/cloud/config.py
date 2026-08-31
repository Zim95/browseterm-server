'''
Cloud configuration boundary.

Cloud code (`app.py`, `src/cloud/*`) should import settings from this module, not from
`src.common.config` directly. `src.common.config` also declares local-only settings (ContainerMaker
host/certs, Socket-SSH URL, payment-gateway host/certs) that the Cloud server must never come to
depend on as P05+ builds real Cloud APIs on top of this skeleton. This module re-exports only the
subset the Cloud server actually owns: PostgreSQL and Redis.

Reuses `src.common.config`'s existing env-var-driven values (and `browseterm-db`'s `DBConfig`)
rather than duplicating them.
'''
import os

from src.common.config import (
    DB_CONFIG,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_USERNAME,
    REDIS_PASSWORD,
    REDIS_DB,
    SNAPSHOT_REGISTRY_REPO_PREFIX,
)

# Interim shared secret gating the internal-only auth/container-write endpoints Local calls
# (src/cloud/auth_handlers.py, container write routes) - not a substitute for the real
# "Cloud is the OAuth client" redesign (plan section 7.1 / P07), which removes the need for
# these endpoints to trust a caller's word for who the user is at all. Must match Local's
# CLOUD_INTERNAL_API_TOKEN.
CLOUD_INTERNAL_API_TOKEN: str = os.getenv("CLOUD_INTERNAL_API_TOKEN", "")

__all__ = [
    "DB_CONFIG",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_USERNAME",
    "REDIS_PASSWORD",
    "REDIS_DB",
    "CLOUD_INTERNAL_API_TOKEN",
    "SNAPSHOT_REGISTRY_REPO_PREFIX",
]
