'''
Mirrors tests/unit/cloud/test_sse_broadcaster.py's own convention: exercise the PGListener
callback directly (the exact call shape PGListener would make with a raw NOTIFY payload string),
no live Postgres LISTEN connection needed.
'''
import asyncio
import json
from unittest import IsolatedAsyncioTestCase

from src.control.command_broadcaster import CommandBroadcaster
from src.control.connection_registry import ConnectionRegistry, CHECK_PENDING_SENTINEL


def _payload(**overrides) -> str:
    data = {
        "id": "cmd-1", "device_id": "device-1", "user_id": "user-1",
        "container_id": "container-1", "operation": "CREATE", "created_at": "2026-09-21T00:00:00Z",
    }
    data.update(overrides)
    return json.dumps(data)


class TestCommandBroadcaster(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.registry = ConnectionRegistry()
        self.registry._connections.clear()
        self.broadcaster = CommandBroadcaster()
        self.broadcaster._loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        self.registry._connections.clear()
        self.broadcaster._loop = None

    async def test_notification_wakes_the_connected_devices_queue(self) -> None:
        state = self.registry.register("device-1", "user-1")
        self.broadcaster._on_command_created(_payload())
        woken = await asyncio.wait_for(state.queue.get(), timeout=1.0)
        self.assertIs(woken, CHECK_PENDING_SENTINEL)

    async def test_notification_for_disconnected_device_does_not_raise(self) -> None:
        self.broadcaster._on_command_created(_payload(device_id="nobody-connected"))  # must not raise

    async def test_notification_does_not_wake_a_different_devices_queue(self) -> None:
        other_state = self.registry.register("device-other", "user-1")
        self.registry.register("device-1", "user-1")
        self.broadcaster._on_command_created(_payload(device_id="device-1"))
        self.assertTrue(other_state.queue.empty())

    async def test_notification_after_reconnect_wakes_only_the_current_connection(self) -> None:
        '''register() replaces the dict entry on a new Hello, so a notification arriving after a
        reconnect can only ever reach the CURRENT connection's queue - the old one is gone from
        the registry entirely, not merely flagged.'''
        first_state = self.registry.register("device-1", "user-1")
        second_state = self.registry.register("device-1", "user-1")
        self.broadcaster._on_command_created(_payload(device_id="device-1"))
        self.assertTrue(first_state.queue.empty())
        woken = await asyncio.wait_for(second_state.queue.get(), timeout=1.0)
        self.assertIs(woken, CHECK_PENDING_SENTINEL)

    async def test_malformed_payload_does_not_raise(self) -> None:
        self.broadcaster._on_command_created("not-json")
