'''
P07 - Cloud-owned OAuth state (Redis-backed, single-use, short-lived).

Protects the OAuth authorization-code flow against CSRF/state-injection: `create_state` mints a
cryptographically random, unguessable value before redirecting the browser to Google/GitHub;
`consume_state` is called exactly once, on the callback, and atomically deletes the key it reads
(GETDEL) so a replayed `state` value - reusing a callback URL, or an attacker racing a second
callback request - can never validate twice. A missing/unknown/expired/already-consumed state all
collapse to the same `None` return; callers must reject all of those identically to avoid leaking
which case occurred.
'''
import json
import secrets
import time
from typing import Optional, TypedDict

import redis

from src.common.config import REDIS_USERNAME, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

OAUTH_STATE_PREFIX = "oauth:state:"
OAUTH_STATE_TTL_SECONDS = 300  # 5 minutes - long enough for a real user to complete provider login


class OAuthStateData(TypedDict):
    provider: str
    target: str
    created_at: float


class OAuthStateManager:
    def __init__(self) -> None:
        self.redis_client: redis.Redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USERNAME, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
        )

    def create_state(self, provider: str, target: str) -> str:
        state = secrets.token_urlsafe(32)
        data: OAuthStateData = {"provider": provider, "target": target, "created_at": time.time()}
        self.redis_client.setex(f"{OAUTH_STATE_PREFIX}{state}", OAUTH_STATE_TTL_SECONDS, json.dumps(data))
        return state

    def consume_state(self, state: str, expected_provider: str) -> Optional[OAuthStateData]:
        '''Single-use: GETDEL removes the key atomically, so a concurrent second read of the same
        state value never both succeed. Returns None for missing/expired/replayed state, or when
        the state's provider doesn't match the callback route it was presented to (a state minted
        for /auth/google/start must not validate on /auth/github/callback).'''
        key = f"{OAUTH_STATE_PREFIX}{state}"
        raw = self.redis_client.getdel(key)
        if raw is None:
            return None
        try:
            data: OAuthStateData = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if data.get("provider") != expected_provider:
            return None
        return data
