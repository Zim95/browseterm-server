'''
Migration Part 12: DeviceControlServicer._handle_local_event (status_monitor's report, forwarded
by Device Agent) and _handle_terminal_tunnel_registration (tunnel_registrar's report, forwarded).
'''
import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from browseterm_db.operations import OperationResult

from src.control.servicer import DeviceControlServicer
from device_control_spec.device_control_types_pb2 import LocalEvent, TerminalTunnelRegistration


class TestHandleLocalEvent(IsolatedAsyncioTestCase):
    @patch("src.control.servicer.DeviceCommandOps")
    async def test_container_status_report_applies_conditional_update(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.conditional_container_update.return_value = OperationResult(success=True, data={"matched": 1})
        event = LocalEvent(event_type="container_status_report", payload_json=json.dumps({
            "container_id": "c1", "placement_generation": 2, "observed_status": "Running", "kubernetes_id": "pod-1",
        }))
        await DeviceControlServicer()._handle_local_event("d1", event)
        container_id, device_id, generation, update_data = mock_ops_cls.return_value.conditional_container_update.call_args[0]
        self.assertEqual(container_id, "c1")
        self.assertEqual(device_id, "d1")
        self.assertEqual(generation, 2)
        self.assertEqual(update_data["status"], "Running")
        self.assertEqual(update_data["kubernetes_id"], "pod-1")

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_unknown_event_type_is_ignored(self, mock_ops_cls) -> None:
        event = LocalEvent(event_type="something_else", payload_json="{}")
        await DeviceControlServicer()._handle_local_event("d1", event)
        mock_ops_cls.return_value.conditional_container_update.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_malformed_payload_does_not_raise(self, mock_ops_cls) -> None:
        event = LocalEvent(event_type="container_status_report", payload_json="not-json")
        await DeviceControlServicer()._handle_local_event("d1", event)  # must not raise
        mock_ops_cls.return_value.conditional_container_update.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    async def test_missing_required_field_is_ignored(self, mock_ops_cls) -> None:
        event = LocalEvent(event_type="container_status_report", payload_json=json.dumps({"container_id": "c1"}))
        await DeviceControlServicer()._handle_local_event("d1", event)
        mock_ops_cls.return_value.conditional_container_update.assert_not_called()


class TestHandleTerminalTunnelRegistration(IsolatedAsyncioTestCase):
    @patch("src.control.servicer.DeviceOps")
    async def test_valid_registration_updates_device(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "tunnel_generation": 1, "tunnel_public_url": "https://old.example.com"},
        )
        mock_ops_cls.return_value.update.return_value = OperationResult(success=True)
        registration = TerminalTunnelRegistration(provider="ngrok", public_url="https://new.example.com", generation=2, status="online")

        await DeviceControlServicer()._handle_terminal_tunnel_registration("d1", registration)

        mock_ops_cls.return_value.update.assert_called_once()
        _, update_data = mock_ops_cls.return_value.update.call_args[0]
        self.assertEqual(update_data["tunnel_public_url"], "https://new.example.com")
        self.assertEqual(update_data["tunnel_generation"], 2)
        self.assertIn("tunnel_connected_at", update_data)

    @patch("src.control.servicer.DeviceOps")
    async def test_stale_generation_is_rejected(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.find_one.return_value = OperationResult(
            success=True, data={"id": "d1", "tunnel_generation": 5, "tunnel_public_url": "https://current.example.com"},
        )
        registration = TerminalTunnelRegistration(provider="ngrok", public_url="https://stale.example.com", generation=2, status="online")

        await DeviceControlServicer()._handle_terminal_tunnel_registration("d1", registration)

        mock_ops_cls.return_value.update.assert_not_called()

    @patch("src.control.servicer.DeviceOps")
    async def test_unknown_device_is_a_no_op(self, mock_ops_cls) -> None:
        mock_ops_cls.return_value.find_one.return_value = OperationResult(success=True, data=None)
        registration = TerminalTunnelRegistration(provider="ngrok", public_url="https://x.example.com", generation=1, status="online")
        await DeviceControlServicer()._handle_terminal_tunnel_registration("d1", registration)  # must not raise
