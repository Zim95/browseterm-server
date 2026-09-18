'''
remotetunelling.md Phase 5 - single-use, container-and-device-bound terminal authorization
tickets. Same Redis-backed, GETDEL-atomic, single-use pattern HandoffManager already established
(src/authentication/handoff_manager.py) - the raw token itself is the Redis key, exactly like
every other one-time credential in this codebase (handoff codes, websocket tokens, sse tokens);
no separate hash is stored, since that's already the existing convention here, not a deviation
from it.

This is deliberately the ONE place "is this browser allowed to open a terminal to this
container, on this device, right now" gets decided - socket-ssh (Phase 7) never re-derives any of
these checks itself, it only ever consumes a ticket this module already validated.
'''
import json
import secrets
import time
from typing import Optional, TypedDict

import redis

from src.common.config import REDIS_USERNAME, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB

TICKET_PREFIX = "terminal:ticket:"

# "Expire after approximately 30 seconds" (remotetunelling.md Phase 5) - long enough for the
# browser to receive the response and open the WebSocket, short enough that a leaked/logged
# ticket is worthless almost immediately.
TICKET_TTL_SECONDS = 30


class TicketData(TypedDict):
    user_id: str
    device_id: str
    container_id: str
    created_at: float


class TerminalTicketManager:
    def __init__(self) -> None:
        self.redis_client: redis.Redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, username=REDIS_USERNAME, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
        )

    def create_ticket(self, user_id: str, device_id: str, container_id: str) -> str:
        ticket = secrets.token_urlsafe(32)
        data: TicketData = {
            "user_id": user_id, "device_id": device_id, "container_id": container_id,
            "created_at": time.time(),
        }
        self.redis_client.setex(f"{TICKET_PREFIX}{ticket}", TICKET_TTL_SECONDS, json.dumps(data))
        return ticket

    def consume_ticket(self, ticket: str) -> Optional[TicketData]:
        '''GETDEL is atomic at the Redis level - concurrent consumption attempts can never both
        succeed (remotetunelling.md: "Consume atomically so simultaneous attempts cannot both
        succeed"). Returns None for a missing/expired/already-consumed ticket - the caller can't
        tell those apart, by design (same "collapse to one failure shape" convention
        HandoffManager already uses for its own consume_handoff).'''
        raw = self.redis_client.getdel(f"{TICKET_PREFIX}{ticket}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
