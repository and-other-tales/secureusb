#!/usr/bin/env python3
"""Unit tests for SecureUSBClient logic running on Linux."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import gi_stubs

gi_stubs.install()

from src.gui.client import SecureUSBClient


class TestSecureUSBClient(unittest.TestCase):
    def setUp(self):
        self.client = SecureUSBClient()
        self.client.send_notification = MagicMock()

    def test_show_notification_uses_gio_helpers(self):
        with patch("src.gui.client.Gio.Notification") as mock_notification, \
             patch("src.gui.client.Gio.ThemedIcon") as mock_icon:
            notification_instance = MagicMock()
            mock_notification.new.return_value = notification_instance
            icon_instance = MagicMock()
            mock_icon.new.return_value = icon_instance

            self.client._show_notification("Device allowed", True)

        mock_notification.new.assert_called_once_with("SecureUSB")
        notification_instance.set_body.assert_called_once_with("Device allowed")
        mock_icon.new.assert_called_once_with("secureusb")
        notification_instance.set_icon.assert_called_once_with(icon_instance)
        self.client.send_notification.assert_called_once()

    def test_check_pending_devices_shows_dialog_for_each_entry(self):
        pending = [
            {"device_id": "1-1", "display_name": "Drive"},
            {"device_id": "2-1", "display_name": "Keyboard"},
        ]
        self.client.dbus_client = MagicMock()
        self.client.dbus_client.interface.GetPendingDevices.return_value = pending

        with patch.object(self.client, "_show_authorization_dialog") as mock_show:
            self.client._check_pending_devices()

        self.assertEqual(mock_show.call_count, 2)
        mock_show.assert_any_call({"device_id": "1-1", "display_name": "Drive"})
        mock_show.assert_any_call({"device_id": "2-1", "display_name": "Keyboard"})

    def test_on_device_disconnected_closes_active_dialog(self):
        dialog = MagicMock()
        self.client.active_dialogs["1-1"] = dialog

        self.client._on_device_disconnected("1-1")

        dialog.close.assert_called_once()
        self.assertNotIn("1-1", self.client.active_dialogs)


if __name__ == "__main__":
    unittest.main()
