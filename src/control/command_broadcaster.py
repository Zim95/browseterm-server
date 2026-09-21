'''
Fans out `device_command_created` Postgres NOTIFY events (browseterm-db migration Part 6) to
whichever device's connection is currently live in this process's ConnectionRegistry. Mirrors
src/cloud/sse_broadcaster.py's SSEBroadcaster pattern exactly (same PGListener usage, same
thread-to-asyncio bridge via loop.call_soon_threadsafe) - see that module for the precedent.

This is a low-latency PUSH path only. It is not the only way a command gets delivered: the
delivery loop (src/control/servicer.py) also queries DeviceCommandOps.find_pending_for_device
right after every Hello/reconnect, which is what actually guarantees "command created while
device was offline is delivered after reconnect" - this broadcaster only shaves latency off the
already-connected case.
'''
import asyncio
import threading
from typing import Optional

from browseterm_db.common.pg_listener import PGListener, DEVICE_COMMAND_CREATED_CHANNEL, DeviceCommandCreatedPayload

from src.cloud.config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
from src.control.connection_registry import connection_registry, CHECK_PENDING_SENTINEL
from src.common.logging_setup import get_logger

logger = get_logger("command_broadcaster")


class CommandBroadcaster:
    _instance: Optional["CommandBroadcaster"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CommandBroadcaster":
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
        self._listener: Optional[PGListener] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._listener = PGListener(
            host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER,
            password=POSTGRES_PASSWORD, database=POSTGRES_DB,
        )
        self._listener.connect()
        self._listener.listen(DEVICE_COMMAND_CREATED_CHANNEL, self._on_command_created)
        self._listener.run_in_thread()
        logger.info("CommandBroadcaster started (Postgres LISTEN)")

    def stop(self) -> None:
        if self._listener:
            self._listener.disconnect()
            self._listener = None
        logger.info("CommandBroadcaster stopped")

    def _on_command_created(self, raw_payload: str) -> None:
        try:
            payload = DeviceCommandCreatedPayload.from_json(raw_payload)
        except Exception:
            logger.error("failed to parse device_command_created payload", exc_info=True)
            return
        state = connection_registry.get(payload.device_id)
        if state is None or state.superseded or not self._loop:
            return  # device not currently connected to THIS replica - fine, delivery loop on
                     # reconnect (or, on multi-replica, the replica actually holding the stream)
                     # will pick it up via find_pending_for_device instead.
        # The queue only ever carries a wake-up signal here, not the command itself - the
        # delivery loop always re-reads from Postgres before sending ExecuteCommand, so it never
        # acts on a stale/racing notification payload.
        self._loop.call_soon_threadsafe(state.queue.put_nowait, CHECK_PENDING_SENTINEL)


command_broadcaster = CommandBroadcaster()
