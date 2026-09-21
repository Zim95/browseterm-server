'''
One end-to-end drive of DeviceControlServicer.Connect() itself, proving the pieces tested in
isolation elsewhere (auth, ConnectionRegistry, pending-command delivery) are actually wired
together correctly: Hello -> HelloAccepted -> initial pending command delivered -> clean
shutdown. Everything below it is unit-tested separately (test_auth.py, test_connection_registry.py,
test_servicer.py) rather than re-proven here.
'''
import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from browseterm_db.operations import OperationResult

from src.control.auth import AuthenticatedDevice
from src.control.connection_registry import connection_registry
from src.control.servicer import DeviceControlServicer
from device_control_spec.device_control_pb2 import DeviceToCloud
from device_control_spec.device_control_types_pb2 import Hello


class _QueueRequestIterator:
    '''A controllable inbound async iterator standing in for the real gRPC request_iterator.'''

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()

    def send(self, message: DeviceToCloud) -> None:
        self._queue.put_nowait(message)

    def __aiter__(self):
        return self

    async def __anext__(self) -> DeviceToCloud:
        return await self._queue.get()


def _command_row(**overrides) -> dict:
    row = {
        "id": "cmd-1", "user_id": "user-1", "device_id": "device-1", "container_id": "container-1",
        "operation": "Create", "placement_generation": 1, "expected_container_state": None,
        "status": "Queued", "attempt_count": 0, "request_id": None, "correlation_id": "trace-1",
    }
    row.update(overrides)
    return row


class TestConnectEndToEnd(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        connection_registry._connections.clear()

    def tearDown(self) -> None:
        connection_registry._connections.clear()

    @patch("src.control.servicer._bump_connection_generation")
    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.authenticate_stream")
    async def test_hello_then_pending_command_then_clean_close(
        self, mock_authenticate, mock_ops_cls, mock_bump,
    ) -> None:
        mock_authenticate.return_value = AuthenticatedDevice(user_id="user-1", device_id="device-1", scopes=[])
        mock_ops = mock_ops_cls.return_value
        mock_ops.find_pending_for_device.return_value = OperationResult(success=True, data=[_command_row()])
        mock_ops.update.return_value = OperationResult(success=True)

        request_iterator = _QueueRequestIterator()
        request_iterator.send(DeviceToCloud(hello=Hello(device_id="device-1", agent_version="0.1.0", protocol_version="v1")))

        context = MagicMock()
        context.invocation_metadata = MagicMock(return_value=[("authorization", "Bearer bst_device_x")])

        servicer = DeviceControlServicer()
        connect_gen = servicer.Connect(request_iterator, context)

        hello_accepted_msg = await asyncio.wait_for(connect_gen.__anext__(), timeout=2.0)
        self.assertEqual(hello_accepted_msg.WhichOneof("payload"), "hello_accepted")
        self.assertEqual(hello_accepted_msg.hello_accepted.connection_generation, 1)

        execute_command_msg = await asyncio.wait_for(connect_gen.__anext__(), timeout=2.0)
        self.assertEqual(execute_command_msg.WhichOneof("payload"), "execute_command")
        self.assertEqual(execute_command_msg.execute_command.command_id, "cmd-1")

        self.assertIsNotNone(connection_registry.get("device-1"))
        await connect_gen.aclose()
        self.assertIsNone(connection_registry.get("device-1"), "Connect()'s cleanup must unregister the connection on close")

    @patch("src.control.servicer._bump_connection_generation")
    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.authenticate_stream")
    async def test_second_connection_supersedes_the_first_and_bumps_generation(
        self, mock_authenticate, mock_ops_cls, mock_bump,
    ) -> None:
        '''Doc-required: "new stream replaces old generation" - proven through the real Connect()
        entrypoint this time, not just ConnectionRegistry directly.'''
        mock_authenticate.return_value = AuthenticatedDevice(user_id="user-1", device_id="device-1", scopes=[])
        mock_ops_cls.return_value.find_pending_for_device.return_value = OperationResult(success=True, data=[])

        def _new_stream():
            request_iterator = _QueueRequestIterator()
            request_iterator.send(DeviceToCloud(hello=Hello(device_id="device-1", agent_version="0.1.0", protocol_version="v1")))
            context = MagicMock()
            context.invocation_metadata = MagicMock(return_value=[("authorization", "Bearer bst_device_x")])
            return DeviceControlServicer().Connect(request_iterator, context)

        first_gen = _new_stream()
        first_hello_accepted = await asyncio.wait_for(first_gen.__anext__(), timeout=2.0)
        self.assertEqual(first_hello_accepted.hello_accepted.connection_generation, 1)

        second_gen = _new_stream()
        second_hello_accepted = await asyncio.wait_for(second_gen.__anext__(), timeout=2.0)
        self.assertEqual(second_hello_accepted.hello_accepted.connection_generation, 2)

        current = connection_registry.get("device-1")
        self.assertEqual(current.generation, 2)

        await first_gen.aclose()
        await second_gen.aclose()

    async def test_wrong_first_message_aborts_the_stream(self) -> None:
        with patch("src.control.servicer.authenticate_stream") as mock_authenticate:
            mock_authenticate.return_value = AuthenticatedDevice(user_id="user-1", device_id="device-1", scopes=[])
            request_iterator = _QueueRequestIterator()
            from device_control_spec.device_control_types_pb2 import Heartbeat
            request_iterator.send(DeviceToCloud(heartbeat=Heartbeat(sent_at_unix_ms=1)))

            context = MagicMock()
            context.invocation_metadata = MagicMock(return_value=[("authorization", "Bearer bst_device_x")])
            context.abort = MagicMock(side_effect=RuntimeError("aborted"))

            servicer = DeviceControlServicer()
            connect_gen = servicer.Connect(request_iterator, context)
            with self.assertRaises(RuntimeError):
                await asyncio.wait_for(connect_gen.__anext__(), timeout=2.0)
            context.abort.assert_called_once()

    async def test_unauthenticated_stream_is_aborted(self) -> None:
        with patch("src.control.servicer.authenticate_stream") as mock_authenticate:
            mock_authenticate.return_value = None
            context = MagicMock()
            context.invocation_metadata = MagicMock(return_value=[])
            context.abort = MagicMock(side_effect=RuntimeError("aborted"))

            servicer = DeviceControlServicer()
            connect_gen = servicer.Connect(_QueueRequestIterator(), context)
            with self.assertRaises(RuntimeError):
                await asyncio.wait_for(connect_gen.__anext__(), timeout=2.0)
            context.abort.assert_called_once()
            args, _ = context.abort.call_args
            import grpc
            self.assertEqual(args[0], grpc.StatusCode.UNAUTHENTICATED)
