'''
P10 - SSEBroadcaster's callback/fan-out logic, exercised directly (no live Postgres LISTEN
connection needed: _on_status_change/_on_save_status_change are the exact callbacks PGListener
would invoke with a raw NOTIFY payload string, so we call them the same way here).
'''
import asyncio
import json
from unittest import IsolatedAsyncioTestCase

from src.cloud.sse_broadcaster import SSEBroadcaster


def _status_payload(**overrides) -> str:
    data = {
        "id": "container-123", "user_id": "user-42", "name": "my-container",
        "old_status": "PENDING", "new_status": "RUNNING", "updated_at": "2026-08-31T00:00:00Z",
    }
    data.update(overrides)
    return json.dumps(data)


def _save_status_payload(**overrides) -> str:
    data = {
        "id": "container-123", "user_id": "user-42", "name": "my-container",
        "save_status": "Succeeded", "saved_image": "registry/my-container:snap", "save_error": None,
        "last_saved_at": "2026-08-31T00:01:00Z", "last_save_attempted_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
    }
    data.update(overrides)
    return json.dumps(data)


class TestSSEBroadcaster(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.broadcaster = SSEBroadcaster()
        with self.broadcaster._queues_lock:
            self.broadcaster._client_queues.clear()
        self.broadcaster._loop = asyncio.get_event_loop()

    def tearDown(self) -> None:
        with self.broadcaster._queues_lock:
            self.broadcaster._client_queues.clear()
        self.broadcaster._loop = None

    async def test_status_change_delivered_to_subscribed_user(self) -> None:
        queue = self.broadcaster.subscribe("user-42")
        self.broadcaster._on_status_change(_status_payload())
        message = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(message["type"], "status_change")
        self.assertEqual(message["container_id"], "container-123")
        self.assertEqual(message["user_id"], "user-42")
        self.assertEqual(message["old_status"], "PENDING")
        self.assertEqual(message["new_status"], "RUNNING")

    async def test_save_status_change_delivered_to_subscribed_user(self) -> None:
        queue = self.broadcaster.subscribe("user-42")
        self.broadcaster._on_save_status_change(_save_status_payload())
        message = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(message["type"], "save_status_change")
        self.assertEqual(message["container_id"], "container-123")
        self.assertEqual(message["save_status"], "Succeeded")
        self.assertEqual(message["saved_image"], "registry/my-container:snap")

    async def test_not_delivered_to_other_users(self) -> None:
        other_queue = self.broadcaster.subscribe("someone-else")
        self.broadcaster.subscribe("user-42")
        self.broadcaster._on_status_change(_status_payload())
        self.assertTrue(other_queue.empty())

    async def test_no_subscribers_does_not_raise(self) -> None:
        self.broadcaster._on_status_change(_status_payload(user_id="nobody-subscribed"))

    async def test_unsubscribe_stops_delivery(self) -> None:
        queue = self.broadcaster.subscribe("user-42")
        self.broadcaster.unsubscribe("user-42", queue)
        self.broadcaster._on_status_change(_status_payload())
        # give the (synchronous, same-thread here) callback a beat - nothing should arrive
        await asyncio.sleep(0)
        self.assertTrue(queue.empty())

    async def test_malformed_payload_does_not_raise(self) -> None:
        self.broadcaster.subscribe("user-42")
        self.broadcaster._on_status_change("not-json")
        self.broadcaster._on_save_status_change("not-json")
