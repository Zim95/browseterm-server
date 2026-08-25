# builtins
import asyncio
import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

# module under test
from src.status_listener import StatusListenerService


class TestSaveStatusChangeBroadcast(IsolatedAsyncioTestCase):
    '''
    Unit tests for StatusListenerService._handle_save_status_change.

    StatusListenerService is a singleton, so we grab the instance, point its event
    loop at the running test loop, subscribe a fake client queue, and feed a JSON
    save payload. We patch ContainerSaveStatusChangePayload.from_json so the test does
    not depend on the exact DB payload schema and needs no live Postgres/PGListener.

    The broadcast uses self._loop.call_soon_threadsafe(...), so we await the queue to
    let the scheduled put_nowait run on the loop.
    '''
    def setUp(self) -> None:
        self.service: StatusListenerService = StatusListenerService()
        self.user_id: str = 'user-42'
        # Reset any queues left over from other tests (singleton state).
        with self.service._queues_lock:
            self.service._client_queues.clear()

    def tearDown(self) -> None:
        with self.service._queues_lock:
            self.service._client_queues.clear()

    def _fake_from_json(self, payload: str) -> SimpleNamespace:
        '''
        Stand-in for ContainerSaveStatusChangePayload.from_json that maps the JSON
        payload onto the attribute names the handler reads.
        '''
        raw: dict = json.loads(payload)
        return SimpleNamespace(
            id=raw['id'],
            user_id=raw['user_id'],
            name=raw['name'],
            save_status=raw['save_status'],
            saved_image=raw.get('saved_image'),
            save_error=raw.get('save_error'),
            last_saved_at=raw.get('last_saved_at'),
            last_save_attempted_at=raw.get('last_save_attempted_at'),
            updated_at=raw.get('updated_at'),
        )

    async def test_save_status_change_broadcast_to_user_queue(self) -> None:
        '''
        A save payload for a subscribed user should enqueue a 'save_status_change'
        message on that user's queue with the mapped fields.
        '''
        # Point the service at the running test loop and subscribe a client.
        self.service._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = self.service.subscribe(self.user_id)

        payload: str = json.dumps({
            'id': 'container-123',
            'user_id': self.user_id,
            'name': 'my-container',
            'save_status': 'SUCCEEDED',
            'saved_image': 'registry/my-container:snap',
            'save_error': None,
            'last_saved_at': '2026-07-18T00:00:00Z',
            'last_save_attempted_at': '2026-07-18T00:00:00Z',
            'updated_at': '2026-07-18T00:00:00Z',
        })

        with patch(
            'src.status_listener.ContainerSaveStatusChangePayload.from_json',
            side_effect=self._fake_from_json,
        ):
            self.service._handle_save_status_change(payload)

            # Let the call_soon_threadsafe callback run and deliver the message.
            message = await asyncio.wait_for(queue.get(), timeout=1.0)

        self.assertEqual(message['type'], 'save_status_change')
        self.assertEqual(message['container_id'], 'container-123')
        self.assertEqual(message['user_id'], self.user_id)
        self.assertEqual(message['name'], 'my-container')
        self.assertEqual(message['save_status'], 'SUCCEEDED')
        self.assertEqual(message['saved_image'], 'registry/my-container:snap')
        self.assertIsNone(message['save_error'])
        self.assertEqual(message['last_saved_at'], '2026-07-18T00:00:00Z')
        self.assertEqual(message['last_save_attempted_at'], '2026-07-18T00:00:00Z')
        self.assertEqual(message['updated_at'], '2026-07-18T00:00:00Z')

    async def test_save_status_change_not_sent_to_other_users(self) -> None:
        '''
        A save payload for one user should not be delivered to a different user's queue.
        '''
        self.service._loop = asyncio.get_running_loop()
        other_queue: asyncio.Queue = self.service.subscribe('someone-else')

        payload: str = json.dumps({
            'id': 'container-123',
            'user_id': self.user_id,
            'name': 'my-container',
            'save_status': 'PENDING',
            'saved_image': None,
            'save_error': None,
            'updated_at': '2026-07-18T00:00:00Z',
        })

        with patch(
            'src.status_listener.ContainerSaveStatusChangePayload.from_json',
            side_effect=self._fake_from_json,
        ):
            self.service._handle_save_status_change(payload)
            # Give the loop a tick; nothing should be enqueued for the other user.
            await asyncio.sleep(0)

        self.assertTrue(other_queue.empty())
