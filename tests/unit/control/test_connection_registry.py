'''
Part 6 required tests covered here: "new stream replaces old generation", "offline detection".
'''
import asyncio
from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from src.control.connection_registry import ConnectionRegistry


class TestConnectionRegistry(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.registry = ConnectionRegistry()
        self.registry._connections.clear()

    def tearDown(self) -> None:
        self.registry._connections.clear()

    async def test_first_registration_starts_at_generation_1(self) -> None:
        state = self.registry.register("device-1", "user-1")
        self.assertEqual(state.generation, 1)
        self.assertFalse(state.superseded)

    async def test_second_hello_for_same_device_bumps_generation_and_supersedes_first(self) -> None:
        '''Doc-required: "new stream replaces old generation."'''
        first = self.registry.register("device-1", "user-1")
        second = self.registry.register("device-1", "user-1")
        self.assertEqual(second.generation, 2)
        self.assertTrue(first.superseded)
        self.assertFalse(second.superseded)
        self.assertIs(self.registry.get("device-1"), second)

    async def test_unregister_only_removes_matching_generation(self) -> None:
        '''A slow cleanup from an already-superseded (old) connection must not delete a newer,
        still-live one - the exact race that made the old find-then-loop-demote pattern unsafe.'''
        self.registry.register("device-1", "user-1")
        second = self.registry.register("device-1", "user-1")

        self.registry.unregister("device-1", 1)  # stale cleanup from the first connection
        self.assertIs(self.registry.get("device-1"), second, "unregister with a stale generation must not remove the current connection")

        self.registry.unregister("device-1", 2)
        self.assertIsNone(self.registry.get("device-1"))

    async def test_is_device_online_true_for_fresh_connection(self) -> None:
        self.registry.register("device-1", "user-1")
        self.assertTrue(self.registry.is_device_online("device-1", threshold_seconds=45))

    async def test_is_device_online_false_when_never_connected(self) -> None:
        self.assertFalse(self.registry.is_device_online("device-nonexistent", threshold_seconds=45))

    async def test_is_device_online_false_past_threshold(self) -> None:
        '''Doc-required: "offline detection" after a configured timeout.'''
        state = self.registry.register("device-1", "user-1")
        state.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=100)
        self.assertFalse(self.registry.is_device_online("device-1", threshold_seconds=45))

    async def test_is_device_online_reflects_only_the_current_registration(self) -> None:
        '''get() only ever exposes the current (non-superseded) connection for a device_id, so
        is_device_online necessarily answers for that one, not any prior superseded connection.'''
        self.registry.register("device-1", "user-1")
        self.registry.register("device-1", "user-1")  # supersedes the first
        self.assertTrue(self.registry.is_device_online("device-1", threshold_seconds=45))

    async def test_touch_ignores_stale_generation(self) -> None:
        self.registry.register("device-1", "user-1")
        second = self.registry.register("device-1", "user-1")
        second.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=100)

        self.registry.touch("device-1", 1)  # stale generation - must not refresh the current one
        self.assertFalse(self.registry.is_device_online("device-1", threshold_seconds=45))

        self.registry.touch("device-1", 2)
        self.assertTrue(self.registry.is_device_online("device-1", threshold_seconds=45))
