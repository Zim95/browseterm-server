'''
Pydantic request models for the Cloud Device API (P05).

Client-supplied identity/state fields (`id`, `user_id`, `used_*`, `status`, `registered_at`,
`last_seen_at`, `revoked_at`) are never declared on these models, so a spoofed value in a request
body simply has nothing to bind to -- the server (`device_handlers.py`) is the only writer of
those fields.
'''
import re
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

# remotetunelling.md: "Accept only: https scheme; Expected ngrok domain patterns for the MVP; a
# URL registered by an authenticated device for itself." Deliberately an allowlist of exact host
# suffixes, not a substring/prefix check - ngrok's own domains for the free/paid tiers in use.
_ALLOWED_TUNNEL_HOST_SUFFIXES = (".ngrok-free.app", ".ngrok.app", ".ngrok.io")


def _validate_tunnel_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("tunnel public_url must use https")
    host = parsed.hostname or ""
    if not any(host.endswith(suffix) for suffix in _ALLOWED_TUNNEL_HOST_SUFFIXES):
        raise ValueError("tunnel public_url must be an ngrok domain")
    return url


class RegisterDeviceRequest(BaseModel):
    '''Body of POST /devices.'''
    device_name: str
    os: str
    architecture: str
    runtime_version: Optional[str] = None

    total_cpu: int = Field(ge=0)
    total_memory_bytes: int = Field(ge=0)
    total_storage_bytes: int = Field(ge=0)

    allocated_cpu: int = Field(ge=0)
    allocated_memory_bytes: int = Field(ge=0)
    allocated_storage_bytes: int = Field(ge=0)

    gpu_info: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def _validate_allocation_within_totals(self) -> "RegisterDeviceRequest":
        if self.allocated_cpu > self.total_cpu:
            raise ValueError("allocated_cpu cannot exceed total_cpu")
        if self.allocated_memory_bytes > self.total_memory_bytes:
            raise ValueError("allocated_memory_bytes cannot exceed total_memory_bytes")
        if self.allocated_storage_bytes > self.total_storage_bytes:
            raise ValueError("allocated_storage_bytes cannot exceed total_storage_bytes")
        return self


# Fields a client may change via POST /devices/{device_id}. Server-controlled identity/state
# fields (id, user_id, used_*, status, registered_at, last_seen_at, revoked_at) are deliberately
# absent -- the update handler drops any of those keys even if present in the request body.
UPDATABLE_DEVICE_FIELDS = frozenset({
    "device_name",
    "runtime_version",
    "total_cpu",
    "total_memory_bytes",
    "total_storage_bytes",
    "allocated_cpu",
    "allocated_memory_bytes",
    "allocated_storage_bytes",
    "gpu_info",
})

# The subset of UPDATABLE_DEVICE_FIELDS that is NOT NULL in the devices table: a client may omit
# these (leaving the stored value untouched) but may not explicitly null them out.
NON_NULLABLE_UPDATE_FIELDS = frozenset({
    "device_name",
    "total_cpu",
    "total_memory_bytes",
    "total_storage_bytes",
    "allocated_cpu",
    "allocated_memory_bytes",
    "allocated_storage_bytes",
})


class UpdateDeviceRequest(BaseModel):
    '''
    Body of POST /devices/{device_id}. Every field is optional (partial update) -- only keys
    actually present in the raw request body are ever written; see `device_handlers.update_device`
    for how presence is tracked separately from this model's post-validation values.
    '''
    device_name: Optional[str] = None
    runtime_version: Optional[str] = None

    total_cpu: Optional[int] = Field(default=None, ge=0)
    total_memory_bytes: Optional[int] = Field(default=None, ge=0)
    total_storage_bytes: Optional[int] = Field(default=None, ge=0)

    allocated_cpu: Optional[int] = Field(default=None, ge=0)
    allocated_memory_bytes: Optional[int] = Field(default=None, ge=0)
    allocated_storage_bytes: Optional[int] = Field(default=None, ge=0)

    gpu_info: Optional[dict[str, Any]] = None


class RegisterTunnelRequest(BaseModel):
    '''Body of POST /devices/{device_id}/tunnel (remotetunelling.md Phase 3/4). provider is
    currently always "ngrok" but kept as a field rather than hardcoded so a future provider
    doesn't need a schema change. generation must be a monotonically increasing counter the
    registrar owns - see device_handlers.register_tunnel for the stale-write rejection.'''
    provider: str
    public_url: str
    generation: int = Field(ge=0)
    status: str = "online"

    @field_validator("public_url")
    @classmethod
    def _validate_public_url(cls, value: str) -> str:
        return _validate_tunnel_url(value)


class TunnelHeartbeatRequest(BaseModel):
    '''Body of POST /devices/{device_id}/tunnel/heartbeat. No public_url here deliberately - a
    heartbeat reaffirms "the tunnel at generation N is still alive", it never changes the URL
    (that's what register_tunnel is for, when the registrar detects an actual change).'''
    generation: int = Field(ge=0)
    status: str = "online"
