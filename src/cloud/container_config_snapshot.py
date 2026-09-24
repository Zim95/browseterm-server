'''
Builds the `container_config_json` snapshot embedded in ExecuteCommand (migration Parts 8/11,
browseterm-device-control-spec's ExecuteCommand.container_config_json) - Cloud resolves
everything Device Agent needs to call Container Maker (image name, resource requests derived
from limits, publish/env config) once, at command-creation time, rather than Device Agent
fetching it separately (the doc's own sanctioned "Cloud sends a strictly typed, validated
configuration snapshot" alternative).
'''
import json
from typing import Optional

from src.cloud.config import RESOURCE_CPU_REQUEST_RATIO, RESOURCE_MEMORY_REQUEST_RATIO, RESOURCE_EPHEMERAL_REQUEST_RATIO
from src.cloud.resource_quantity import derive_cpu_request_string, derive_memory_request_string

# Matches browseterm-server-local's containers_service.py hardcoded SSH publish defaults - the
# only publish shape this product currently creates (one SSH port per terminal).
_DEFAULT_PUBLISH_INFORMATION = [{"publish_port": 2222, "target_port": 22, "protocol": "TCP", "node_port": None}]


def build_create_config_json(container: dict, image_name: str) -> str:
    return _build(container, image_name=image_name)


def build_resume_config_json(container: dict) -> str:
    '''Uses container["saved_image"] exactly as stored - no digest/immutability redesign, per
    the migration doc's revised Part 11.'''
    return _build(container, saved_image=container.get("saved_image"))


def _build(container: dict, image_name: Optional[str] = None, saved_image: Optional[str] = None) -> str:
    cfg = {
        "container_name": container["name"],
        "network_name": f"{container['user_id']}-namespace",
        "exposure_level": 0,
        "publish_information": container.get("port_mappings") or _DEFAULT_PUBLISH_INFORMATION,
        # CONTAINER_ID rides in environment_variables (not a dedicated field) so container-maker's
        # pod_manager.py can stamp it as the browseterm/container-id pod label with no protocol
        # change - matches browseterm-server-local's old resume_container, which explicitly added
        # this on top of the container's own stored env vars. Dropped by this migration's rewrite
        # (this function just passed environment_vars through verbatim) - a real, high-impact bug:
        # status_monitor's resource_reconciler.py reads that exact label to know which DB
        # container_id a live pod belongs to (running_container_ids()). Without it, every
        # genuinely-running pod looked invisible to the reconciler, which then called
        # mark_lost_if_running on every one of them on its next 5-minute pass - silently flipping
        # healthy, running containers to HIBERNATED with no device_commands row to explain why.
        "environment_variables": {**(container.get("environment_vars") or {}), "CONTAINER_ID": container["id"]},
        "cpu_request": derive_cpu_request_string(container["cpu_limit"], RESOURCE_CPU_REQUEST_RATIO),
        "cpu_limit": container["cpu_limit"],
        "memory_request": derive_memory_request_string(container["memory_limit"], RESOURCE_MEMORY_REQUEST_RATIO),
        "memory_limit": container["memory_limit"],
        "ephemeral_request": derive_memory_request_string(container["storage_limit"], RESOURCE_EPHEMERAL_REQUEST_RATIO),
        "ephemeral_limit": container["storage_limit"],
        "snapshot_size_limit": None,
    }
    if image_name is not None:
        cfg["image_name"] = image_name
    if saved_image is not None:
        cfg["saved_image"] = saved_image
    return json.dumps(cfg)


def build_delete_config_json(container: dict) -> str:
    return json.dumps({"network_name": f"{container['user_id']}-namespace"})


def build_hibernate_config_json(container: dict) -> str:
    return json.dumps({"network_name": f"{container['user_id']}-namespace"})


def build_save_config_json(container: dict) -> str:
    '''Same shape as Hibernate's - the save step itself only needs network_name to locate the
    pod; SAVE just never proceeds to a delete step afterward.'''
    return json.dumps({"network_name": f"{container['user_id']}-namespace"})
