'''
Migration Part 14: _maybe_activate_on_startup - "A real Desktop/CLI startup may request
activation once... gRPC reconnects reuse the startup ID and must not cause another activation."
'''
from unittest import TestCase
from unittest.mock import MagicMock, patch

from browseterm_db.operations import OperationResult

from src.control.servicer import _maybe_activate_on_startup


class TestMaybeActivateOnStartup(TestCase):
    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.DB_CONFIG")
    def test_empty_startup_id_never_activates(self, mock_db_config, mock_command_ops_cls) -> None:
        _maybe_activate_on_startup("u1", "d1", "")
        mock_db_config.get_db_session.assert_not_called()
        mock_command_ops_cls.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.DB_CONFIG")
    def test_new_startup_id_activates(self, mock_db_config, mock_command_ops_cls) -> None:
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = ("old-startup-id",)
        mock_db_config.get_db_session.return_value = session
        mock_command_ops_cls.return_value.activate_device.return_value = OperationResult(success=True)

        _maybe_activate_on_startup("u1", "d1", "new-startup-id")

        mock_command_ops_cls.return_value.activate_device.assert_called_once_with("u1", "d1")
        session.commit.assert_called_once()

    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.DB_CONFIG")
    def test_same_startup_id_is_a_reconnect_not_a_new_activation(self, mock_db_config, mock_command_ops_cls) -> None:
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = ("same-startup-id",)
        mock_db_config.get_db_session.return_value = session

        _maybe_activate_on_startup("u1", "d1", "same-startup-id")

        mock_command_ops_cls.return_value.activate_device.assert_not_called()
        session.commit.assert_not_called()

    @patch("src.control.servicer.DeviceCommandOps")
    @patch("src.control.servicer.DB_CONFIG")
    def test_unknown_device_does_not_raise(self, mock_db_config, mock_command_ops_cls) -> None:
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        mock_db_config.get_db_session.return_value = session

        _maybe_activate_on_startup("u1", "d1", "new-startup-id")  # must not raise

        mock_command_ops_cls.return_value.activate_device.assert_not_called()
