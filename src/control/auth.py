'''
Device Control stream authentication. Reuses the SAME per-device Bearer credential
(src.authentication.device_token_manager.DeviceTokenManager) already used for the HTTP Device
API (src/cloud/device_handlers.py's authenticate_device) - one device identity, two transports.
'''
import asyncio
from dataclasses import dataclass
from typing import Optional

import grpc

from browseterm_db.operations.all_operations import DeviceOps
from browseterm_db.models.devices import DeviceStatus

from src.authentication.device_token_manager import DeviceTokenManager
from src.cloud.config import DB_CONFIG


@dataclass
class AuthenticatedDevice:
    user_id: str
    device_id: str
    scopes: list


async def authenticate_stream(context: grpc.aio.ServicerContext) -> Optional[AuthenticatedDevice]:
    '''
    Validates the Bearer device token carried in gRPC metadata (key "authorization", same header
    name/format as the HTTP path: "Bearer <token>"). Returns None on any failure - callers must
    abort the stream with UNAUTHENTICATED, never fall back to trusting a client-supplied
    device_id/user_id (matches the existing HTTP authenticate_device's own rule).
    '''
    metadata = dict(context.invocation_metadata())
    auth_header = metadata.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    raw_token = auth_header[len("Bearer "):].strip()
    if not raw_token:
        return None

    token_data = await asyncio.to_thread(DeviceTokenManager().validate_token, raw_token)
    if not token_data:
        return None

    device_ops = DeviceOps(DB_CONFIG)
    result = await asyncio.to_thread(
        device_ops.find_one, {"id": token_data["device_id"], "user_id": token_data["user_id"]},
    )
    if not result.data:
        return None
    if result.data["status"] == DeviceStatus.REVOKED.value or result.data.get("revoked_at"):
        return None

    return AuthenticatedDevice(
        user_id=token_data["user_id"], device_id=token_data["device_id"], scopes=token_data.get("scopes", []),
    )
