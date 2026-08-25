"""
Status listener service using PGListener for container status changes.
Provides SSE endpoint for real-time status updates to frontend.
"""

import asyncio
import json
from typing import Dict, Set, Optional
from collections import defaultdict
import threading

from browseterm_db.common.pg_listener import (
    PGListener,
    CONTAINER_STATUS_CHANGE_CHANNEL,
    CONTAINER_SAVE_STATUS_CHANGE_CHANNEL,
    ContainerStatusChangePayload,
    ContainerSaveStatusChangePayload
)

from src.common.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB
)
from src.common.logging_setup import get_logger

logger = get_logger("status_listener")


class StatusListenerService:
    """
    Singleton service that listens for container status changes via PostgreSQL NOTIFY
    and broadcasts them to connected SSE clients.
    """
    _instance: Optional['StatusListenerService'] = None
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
        self._running = False

        # Map of user_id -> set of asyncio.Queue for SSE clients
        self._client_queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._queues_lock = threading.Lock()

        # Event loop reference for cross-thread communication
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop = None):
        """Start the PGListener in a background thread."""
        if self._running:
            return

        self._loop = loop or asyncio.get_event_loop()

        self._listener = PGListener(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        self._listener.connect()
        self._listener.listen(CONTAINER_STATUS_CHANGE_CHANNEL, self._handle_status_change)
        self._listener.listen(CONTAINER_SAVE_STATUS_CHANGE_CHANNEL, self._handle_save_status_change)
        self._listener.run_in_thread()
        self._running = True
        logger.info(
            "StatusListenerService started",
            extra={"channels": [CONTAINER_STATUS_CHANGE_CHANNEL, CONTAINER_SAVE_STATUS_CHANGE_CHANNEL]},
        )

    def stop(self):
        """Stop the PGListener."""
        if self._listener:
            self._listener.disconnect()
            self._listener = None
        self._running = False
        logger.info("StatusListenerService stopped")

    def _handle_status_change(self, payload: str):
        """
        Handle incoming status change notification from PostgreSQL.
        This runs in the PGListener thread, so we need to use thread-safe
        communication to the asyncio event loop.
        """
        try:
            data = ContainerStatusChangePayload.from_json(payload)
            logger.info(
                "status change",
                extra={
                    "container_id": data.id,
                    "container_name": data.name,
                    "old_status": data.old_status,
                    "new_status": data.new_status,
                },
            )

            # Broadcast to all clients subscribed to this user_id
            user_id = data.user_id
            message = {
                'type': 'status_change',
                'container_id': data.id,
                'user_id': data.user_id,
                'name': data.name,
                'old_status': data.old_status,
                'new_status': data.new_status,
                'updated_at': data.updated_at
            }

            with self._queues_lock:
                queues = self._client_queues.get(user_id, set()).copy()

            if queues and self._loop:
                for queue in queues:
                    # Schedule the put on the event loop thread
                    self._loop.call_soon_threadsafe(
                        lambda q=queue, m=message: q.put_nowait(m)
                    )

        except Exception:
            logger.error("error handling status change", exc_info=True)

    def _handle_save_status_change(self, payload: str):
        """
        Handle incoming SAVE status change notification from PostgreSQL and broadcast
        it to the user's SSE clients (same queues as pod-status changes, distinguished
        by the 'save_status_change' type).
        """
        try:
            data = ContainerSaveStatusChangePayload.from_json(payload)
            logger.info(
                "save status change",
                extra={"container_id": data.id, "container_name": data.name, "save_status": data.save_status},
            )

            user_id = data.user_id
            message = {
                'type': 'save_status_change',
                'container_id': data.id,
                'user_id': data.user_id,
                'name': data.name,
                'save_status': data.save_status,
                'saved_image': data.saved_image,
                'save_error': data.save_error,
                'last_saved_at': data.last_saved_at,
                'last_save_attempted_at': data.last_save_attempted_at,
                'updated_at': data.updated_at
            }

            with self._queues_lock:
                queues = self._client_queues.get(user_id, set()).copy()

            if queues and self._loop:
                for queue in queues:
                    self._loop.call_soon_threadsafe(
                        lambda q=queue, m=message: q.put_nowait(m)
                    )

        except Exception:
            logger.error("error handling save status change", exc_info=True)

    def subscribe(self, user_id: str) -> asyncio.Queue:
        """
        Subscribe a client to status updates for a specific user.
        Returns an asyncio.Queue that will receive status change messages.
        """
        queue = asyncio.Queue()
        with self._queues_lock:
            self._client_queues[user_id].add(queue)
        logger.info(
            "client subscribed",
            extra={"user_id": user_id, "total_clients": len(self._client_queues[user_id])},
        )
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue):
        """Unsubscribe a client from status updates."""
        with self._queues_lock:
            if user_id in self._client_queues:
                self._client_queues[user_id].discard(queue)
                if not self._client_queues[user_id]:
                    del self._client_queues[user_id]
        logger.info("client unsubscribed", extra={"user_id": user_id})


# Global instance
status_listener_service = StatusListenerService()
