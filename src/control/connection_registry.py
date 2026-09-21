'''
In-memory registry of live Device Control connections.

"Never use the in-memory connection registry as durable truth" (migration doc, Part 6) - this
tracks only which stream, in THIS process, is currently authoritative for delivering commands to
a given device. Durable state (device online/offline per the DB, command status) always lives in
Postgres via browseterm-db.

Part 6 documents a single control-service replica for the first deployment (see grpc_server.py's
own docstring) - this registry is intentionally process-local, not shared/replicated. A future
multi-replica control service would need to replace this with a shared registry (Redis) keyed by
which replica owns which device's stream; not built here because it isn't needed yet.
'''
import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class ConnectionState:
    device_id: str
    user_id: str
    generation: int
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Set on the previous entry when a new Hello for the same device replaces it - the old
    # Connect() handler's read loop checks this to know it must stop delivering/close cleanly
    # instead of continuing to serve a superseded stream.
    superseded: bool = False


class ConnectionRegistry:
    '''Singleton, mirroring SSEBroadcaster's own singleton pattern in src/cloud/sse_broadcaster.py.'''

    _instance: Optional["ConnectionRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConnectionRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._connections: Dict[str, ConnectionState] = {}
        self._lock2 = threading.Lock()

    def register(self, device_id: str, user_id: str) -> ConnectionState:
        '''New authenticated Hello for device_id: bump the generation, mark any existing
        connection for this device as superseded (its own handler is responsible for noticing and
        closing), and install the new one as current. "New stream replaces old generation."'''
        with self._lock2:
            previous = self._connections.get(device_id)
            new_generation = (previous.generation + 1) if previous else 1
            if previous is not None:
                previous.superseded = True
            state = ConnectionState(device_id=device_id, user_id=user_id, generation=new_generation)
            self._connections[device_id] = state
            return state

    def unregister(self, device_id: str, generation: int) -> None:
        '''Only removes the entry if it is still the one for this generation - a slow cleanup
        from an already-superseded connection must never delete a newer, still-live one.'''
        with self._lock2:
            current = self._connections.get(device_id)
            if current is not None and current.generation == generation:
                del self._connections[device_id]

    def get(self, device_id: str) -> Optional[ConnectionState]:
        with self._lock2:
            return self._connections.get(device_id)

    def touch(self, device_id: str, generation: int) -> None:
        '''Record activity (any inbound message, not just Heartbeat) for offline detection.'''
        with self._lock2:
            current = self._connections.get(device_id)
            if current is not None and current.generation == generation:
                current.last_seen_at = datetime.now(timezone.utc)

    def all_connected_device_ids(self) -> list:
        with self._lock2:
            return list(self._connections.keys())

    def is_device_online(self, device_id: str, threshold_seconds: int) -> bool:
        '''"Mark offline after a configured timeout" (Part 6) - derived from this replica's own
        connection state (whether a stream exists at all, and whether it has been heard from
        recently enough), not from browseterm-db's devices.status column. That column's
        ACTIVE/INACTIVE values currently conflate "eligible for placement" with "connected" (see
        Part 1's progress-log note) - disentangling and persisting connectivity there belongs to
        Part 14, not this part.'''
        state = self.get(device_id)
        if state is None or state.superseded:
            return False
        age_seconds = (datetime.now(timezone.utc) - state.last_seen_at).total_seconds()
        return age_seconds < threshold_seconds


connection_registry = ConnectionRegistry()

# Pushed onto a ConnectionState.queue by CommandBroadcaster (a different thread) to wake the
# owning connection's write loop and ask it to re-check for pending commands, WITHOUT the
# broadcaster itself touching the database from a non-asyncio thread. Defined here (not in
# command_broadcaster.py or servicer.py) so both can import it without a circular import.
CHECK_PENDING_SENTINEL = object()
