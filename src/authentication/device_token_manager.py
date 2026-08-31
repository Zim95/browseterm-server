'''
P07 - Per-device Bearer credential (Redis-backed, opaque, one credential per registered device).

Distinct from the browser/WebView session credential (session_manager.py) - see p07.md section
16: "these are DIFFERENT credentials, do not reuse the same token for both." A device token is
minted exactly once, at device-bootstrap time (oauth_handlers.device_bootstrap_redeem), and is
independently expiring/revocable per device: revoking/expiring device D2's token must never
affect D1's token or the user's browser session (enforced structurally here - each token is its
own Redis key, keyed by a hash of the token itself, not by user_id or device_id, so there is no
shared record two devices could collide on).

Only the SHA-256 hash of the raw token is ever stored (`bst_device_<random>` is only ever
returned once, at issuance, to the caller - Desktop is responsible for putting it straight into
Keychain, see browseterm-desktop's desktop/keychain.py).
'''
import hashlib
import json
import secrets
import time
from typing import Optional, TypedDict

import redis

from src.common.config import REDIS_USERNAME, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

DEVICE_TOKEN_PREFIX = "auth:device:"
DEVICE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 90  # 90 days - long-lived relative to the browser session
                                               # (30 min sliding), matching p07.md section 32's
                                               # "device credential: longer-lived" guidance. Desktop
                                               # re-bootstraps (via a fresh WebView login) if this
                                               # expires; no separate refresh flow implemented.
TOKEN_PREFIX = "bst_device_"


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class DeviceTokenData(TypedDict):
    user_id: str
    device_id: str
    scopes: list


class DeviceTokenManager:
    def __init__(self) -> None:
        self.redis_client: redis.Redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USERNAME, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
        )

    def issue_token(self, user_id: str, device_id: str, scopes: list) -> str:
        '''Returns the raw bearer token. Only the caller sees this raw value - never logged, never
        stored anywhere but the caller's own hands (Desktop -> Keychain).'''
        raw_token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        data: DeviceTokenData = {"user_id": user_id, "device_id": device_id, "scopes": scopes}
        self.redis_client.setex(
            f"{DEVICE_TOKEN_PREFIX}{_hash_token(raw_token)}", DEVICE_TOKEN_TTL_SECONDS, json.dumps(data)
        )
        return raw_token

    def validate_token(self, raw_token: str) -> Optional[DeviceTokenData]:
        raw = self.redis_client.get(f"{DEVICE_TOKEN_PREFIX}{_hash_token(raw_token)}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def revoke_token(self, raw_token: str) -> None:
        '''No HTTP endpoint calls this yet (out of P07 scope - P05 has no device-revoke route
        either, per p07.md section 33) but the storage model already supports it: deleting this
        one key stops only this one device's token from authenticating, leaving every other
        device token and the user's browser session untouched.'''
        self.redis_client.delete(f"{DEVICE_TOKEN_PREFIX}{_hash_token(raw_token)}")
