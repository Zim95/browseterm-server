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

# remotetunelling.md: "offline threshold: 60-90 seconds" - a device/tunnel counts as online for
# terminal-session purposes only if its last tunnel heartbeat is within this window. The
# registrar's own default heartbeat interval is 20s (browseterm_workload/tunnel_registrar), so
# 90s tolerates a couple of missed/delayed heartbeats before treating it as actually offline.
TUNNEL_OFFLINE_THRESHOLD_SECONDS: int = int(os.getenv("TUNNEL_OFFLINE_THRESHOLD_SECONDS", "90"))

# status_monitor's periodic "does the DB's idea of what's Running still have a live pod behind
# it" safety net (see src/cloud/container_handlers.py::list_active_containers_for_device) only
# considers a Running container eligible to be flagged missing once it's been Running for at
# least this long. A container that JUST transitioned to Running (e.g. the live pod_watcher wrote
# it a moment ago) may not yet be visible in status_monitor's own independently-fetched pod list
# purely due to normal timing skew between two separate reads - without this grace window a
# perfectly healthy, brand-new container could be wrongly hibernated out from under a live pod.
LOST_CONTAINER_GRACE_SECONDS: int = int(os.getenv("LOST_CONTAINER_GRACE_SECONDS", "90"))

# Migration Parts 8-11: request-from-limit ratios for the container_config_json snapshot Cloud
# builds for Device Agent - same defaults browseterm-server-local's RESOURCE_*_REQUEST_RATIO
# already used, so a Device Agent-created pod gets identical requests to what Local created.
RESOURCE_CPU_REQUEST_RATIO: float = float(os.getenv("RESOURCE_CPU_REQUEST_RATIO", "0.1"))
RESOURCE_MEMORY_REQUEST_RATIO: float = float(os.getenv("RESOURCE_MEMORY_REQUEST_RATIO", "0.5"))
RESOURCE_EPHEMERAL_REQUEST_RATIO: float = float(os.getenv("RESOURCE_EPHEMERAL_REQUEST_RATIO", "0.5"))

# Migration Part 3 "Preserve compatibility during migration" feature flags. Default False in
# development/this session - production defaults at final cutover must flip these on (Part 20/25),
# not done here since that is a deployment-time decision, not a code default.
DEVICE_COMMAND_CREATE_ENABLED: bool = os.getenv("DEVICE_COMMAND_CREATE_ENABLED", "false").lower() == "true"
DEVICE_COMMAND_DELETE_ENABLED: bool = os.getenv("DEVICE_COMMAND_DELETE_ENABLED", "false").lower() == "true"
DEVICE_COMMAND_HIBERNATE_ENABLED: bool = os.getenv("DEVICE_COMMAND_HIBERNATE_ENABLED", "false").lower() == "true"
DEVICE_COMMAND_RESUME_ENABLED: bool = os.getenv("DEVICE_COMMAND_RESUME_ENABLED", "false").lower() == "true"
# SAVE (not one of the doc's original 25 parts - added 2026-09-22): snapshots a container without
# deleting it. Wired identically to the four flags above.
DEVICE_COMMAND_SAVE_ENABLED: bool = os.getenv("DEVICE_COMMAND_SAVE_ENABLED", "false").lower() == "true"

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
    "TUNNEL_OFFLINE_THRESHOLD_SECONDS",
    "LOST_CONTAINER_GRACE_SECONDS",
    "RESOURCE_CPU_REQUEST_RATIO",
    "RESOURCE_MEMORY_REQUEST_RATIO",
    "RESOURCE_EPHEMERAL_REQUEST_RATIO",
    "DEVICE_COMMAND_CREATE_ENABLED",
    "DEVICE_COMMAND_DELETE_ENABLED",
    "DEVICE_COMMAND_HIBERNATE_ENABLED",
    "DEVICE_COMMAND_RESUME_ENABLED",
    "DEVICE_COMMAND_SAVE_ENABLED",
]
