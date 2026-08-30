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
from src.common.config import (
    DB_CONFIG,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_DB,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_USERNAME,
    REDIS_PASSWORD,
    REDIS_DB,
)

__all__ = [
    "DB_CONFIG",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_DB",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_USERNAME",
    "REDIS_PASSWORD",
    "REDIS_DB",
]
