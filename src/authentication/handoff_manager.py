'''
P07 - One-time Browseterm auth handoff (Redis-backed, single-use, short-lived, purpose-bound).

Two purposes exist:
  - "local_login": minted by the OAuth callback after a session already exists (see
    oauth_handlers.py); redeeming it just returns that existing session's data. It is NOT the
    session token itself - only temporary authorization for Local to complete login.
  - "device_bootstrap": minted by Local's own `/device/bootstrap` (internal-token-gated, after
    Local has already verified the caller's browser session) so Desktop's native code can
    register/refresh its device credential without ever holding the browser's session cookie as
    a long-lived credential. See device_bootstrap_redeem in oauth_handlers.py.

Same single-use guarantee as OAuthStateManager (GETDEL), and the same "wrong purpose fails
exactly like missing/expired" collapsing - a local_login code must never redeem as a device
bootstrap or vice versa.
'''
import json
import secrets
import time
from typing import Literal, Optional, TypedDict

import redis

from src.common.config import REDIS_USERNAME, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

HANDOFF_PREFIX = "auth:handoff:"

Purpose = Literal["local_login", "device_bootstrap"]

# local_login is redeemed by Local within a couple of redirects of the callback firing; keep it
# short. device_bootstrap is redeemed by Desktop's own follow-up HTTP call, immediately after
# Local mints it - same short window is appropriate.
HANDOFF_TTL_SECONDS: dict = {"local_login": 120, "device_bootstrap": 120}


class HandoffData(TypedDict):
    purpose: str
    user_id: str
    session_id: Optional[str]
    created_at: float


class HandoffManager:
    def __init__(self) -> None:
        self.redis_client: redis.Redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USERNAME, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
        )

    def create_handoff(self, purpose: Purpose, user_id: str, session_id: Optional[str] = None) -> str:
        code = secrets.token_urlsafe(32)
        data: HandoffData = {
            "purpose": purpose, "user_id": user_id, "session_id": session_id, "created_at": time.time(),
        }
        self.redis_client.setex(f"{HANDOFF_PREFIX}{code}", HANDOFF_TTL_SECONDS[purpose], json.dumps(data))
        return code

    def consume_handoff(self, code: str, expected_purpose: Purpose) -> Optional[HandoffData]:
        raw = self.redis_client.getdel(f"{HANDOFF_PREFIX}{code}")
        if raw is None:
            return None
        try:
            data: HandoffData = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if data.get("purpose") != expected_purpose:
            return None
        return data
