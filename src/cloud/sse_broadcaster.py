"""
P10 (see ~/browseterm/p.md's "P10" section): Cloud owns Postgres LISTEN/NOTIFY directly and
fans notifications out to per-user asyncio.Queue subscribers for the SSE endpoint
(src/cloud/sse_handlers.py) to read from. Replaces browseterm-server-local's old
status_listener.py, which had to poll Cloud's own /containers API on an interval because Local
holds no Postgres client at all - Cloud does, so it can listen for real instead.

browseterm_db.common.pg_listener.PGListener is a synchronous, thread-based client (psycopg2, not
asyncio) - it already existed as scaffolding (channel names, payload dataclasses) before this
task, built for exactly this usage. It runs LISTEN in a background thread; this module bridges
its thread-based callbacks into the asyncio event loop the FastAPI app runs on via
loop.call_soon_threadsafe, the standard pattern for a non-async callback source feeding
asyncio.Queue consumers safely.
"""
import asyncio
import threading
from collections import defaultdict
from typing import Dict, Optional, Set

from browseterm_db.common.pg_listener import (
    PGListener,
    CONTAINER_STATUS_CHANGE_CHANNEL,
    CONTAINER_SAVE_STATUS_CHANGE_CHANNEL,
    ContainerStatusChangePayload,
    ContainerSaveStatusChangePayload,
)

from src.cloud.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
from src.common.logging_setup import get_logger

logger = get_logger("sse_broadcaster")


class SSEBroadcaster:
    """
    Singleton: owns the PGListener background thread and the per-user set of asyncio.Queue
    subscribers SSE connections read from.
    """
    _instance: Optional["SSEBroadcaster"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._listener: Optional[PGListener] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client_queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._queues_lock = threading.Lock()

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Connect to Postgres and start LISTENing in a background thread."""
        self._loop = loop or asyncio.get_event_loop()
        self._listener = PGListener(
            host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER,
            password=POSTGRES_PASSWORD, database=POSTGRES_DB,
        )
        self._listener.connect()
        self._listener.listen(CONTAINER_STATUS_CHANGE_CHANNEL, self._on_status_change)
        self._listener.listen(CONTAINER_SAVE_STATUS_CHANGE_CHANNEL, self._on_save_status_change)
        self._listener.run_in_thread()
        logger.info("SSEBroadcaster started (Postgres LISTEN)")

    def stop(self) -> None:
        if self._listener:
            self._listener.disconnect()
            self._listener = None
        logger.info("SSEBroadcaster stopped")

    def _on_status_change(self, raw_payload: str) -> None:
        try:
            payload = ContainerStatusChangePayload.from_json(raw_payload)
        except Exception:
            logger.error("failed to parse container_status_change payload", exc_info=True)
            return
        # Field names here match what browseterm-server-local's old status_listener.py used to
        # emit (container_id, not the dataclass's own `id`) - the frontend JS reading these
        # messages (terminals.js/terminalpage.js) is unchanged by P10 except for the connection
        # target, so the message shape has to stay exactly the same.
        message = {
            "type": "status_change",
            "container_id": payload.id,
            "user_id": payload.user_id,
            "name": payload.name,
            "old_status": payload.old_status,
            "new_status": payload.new_status,
            "updated_at": payload.updated_at,
        }
        self._broadcast(payload.user_id, message)

    def _on_save_status_change(self, raw_payload: str) -> None:
        try:
            payload = ContainerSaveStatusChangePayload.from_json(raw_payload)
        except Exception:
            logger.error("failed to parse container_save_status_change payload", exc_info=True)
            return
        message = {
            "type": "save_status_change",
            "container_id": payload.id,
            "user_id": payload.user_id,
            "name": payload.name,
            "save_status": payload.save_status,
            "saved_image": payload.saved_image,
            "save_error": payload.save_error,
            "last_saved_at": payload.last_saved_at,
            "last_save_attempted_at": payload.last_save_attempted_at,
            "updated_at": payload.updated_at,
        }
        self._broadcast(payload.user_id, message)

    def _broadcast(self, user_id: str, message: dict) -> None:
        with self._queues_lock:
            queues = self._client_queues.get(user_id, set()).copy()
        if not queues or not self._loop:
            return
        for queue in queues:
            self._loop.call_soon_threadsafe(queue.put_nowait, message)

    def subscribe(self, user_id: str) -> asyncio.Queue:
        """Subscribe a client to status updates for a specific user. Never trust a
        client-supplied user_id here - the caller must have resolved it from a validated
        session/sse_token first (see sse_handlers.py)."""
        queue: asyncio.Queue = asyncio.Queue()
        with self._queues_lock:
            self._client_queues[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue) -> None:
        with self._queues_lock:
            if user_id in self._client_queues:
                self._client_queues[user_id].discard(queue)
                if not self._client_queues[user_id]:
                    del self._client_queues[user_id]


sse_broadcaster = SSEBroadcaster()
