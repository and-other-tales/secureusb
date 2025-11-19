#!/usr/bin/env python3
"""Targeted tests for SecureUSBDaemon logic on Linux."""

import unittest
from unittest.mock import MagicMock, patch

from src.daemon.service import SecureUSBDaemon
from src.utils.logger import EventAction


class TestSecureUSBDaemon(unittest.TestCase):
    def _daemon_stub(self):
        daemon = SecureUSBDaemon.__new__(SecureUSBDaemon)
        daemon.logger = MagicMock()
        daemon.dbus_service = MagicMock()
        daemon.whitelist = MagicMock()
        daemon.whitelist.is_whitelisted.return_value = False
        daemon.config = MagicMock()
        daemon.storage = MagicMock()
        daemon.recovery_codes = ["HASH1"]
        daemon.timeout_timers = {}
        daemon.pending_authorizations = {}
        return daemon

    @patch("src.daemon.service.GLib.source_remove")
    @patch("src.daemon.service.USBAuthorization.allow_device", return_value=True)
    def test_handle_authorization_request_full(self, mock_allow, mock_remove):
        daemon = self._daemon_stub()
        daemon._verify_authentication = MagicMock(return_value=True)

        device_info = {
            "device_id": "1-1",
            "device_path": "/sys/bus/usb/devices/1-1",
            "vendor_id": "046d",
            "product_id": "c52b",
            "vendor_name": "Foo",
            "product_name": "Bar",
            "serial_number": "ABC",
        }
        daemon.timeout_timers["1-1"] = 123
        daemon.pending_authorizations["1-1"] = device_info.copy()

        result = daemon._handle_authorization_request(device_info, "123456", "full")

        self.assertEqual(result, "success")
        mock_allow.assert_called_once_with("1-1")
        daemon.logger.log_event.assert_any_call(
            EventAction.DEVICE_AUTHORIZED,
            device_path="/sys/bus/usb/devices/1-1",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Foo",
            product_name="Bar",
            serial_number="ABC",
            auth_method="totp",
            success=True,
        )
        daemon.dbus_service.emit_authorization_result.assert_called_once_with("1-1", "authorized", True)
        mock_remove.assert_called_once_with(123)

    @patch("src.daemon.service.GLib.source_remove")
    def test_handle_authorization_auth_failure_logs_event(self, mock_remove):
        daemon = self._daemon_stub()
        daemon._verify_authentication = MagicMock(return_value=False)

        device_info = {
            "device_id": "2-1",
            "device_path": "/sys",
            "vendor_id": "0000",
            "product_id": "0000",
            "serial_number": "DEF",
        }

        result = daemon._handle_authorization_request(device_info, "bad", "full")

        self.assertEqual(result, "auth_failed")
        daemon.logger.log_event.assert_any_call(
            EventAction.AUTH_FAILED,
            device_path="/sys",
            vendor_id="0000",
            product_id="0000",
            serial_number="DEF",
            success=False,
            details="Invalid TOTP code or recovery code",
        )
        mock_remove.assert_not_called()

    def test_verify_authentication_prefers_recovery_codes(self):
        daemon = self._daemon_stub()
        daemon.totp_auth = MagicMock()
        daemon.totp_auth.verify_code.return_value = False
        daemon.storage.remove_recovery_code.return_value = True

        with patch("src.daemon.service.RecoveryCodeManager.verify_code", return_value=True):
            self.assertTrue(daemon._verify_authentication("123456"))

        self.assertEqual(daemon.recovery_codes, [])
        daemon.storage.remove_recovery_code.assert_called_once_with("HASH1")


if __name__ == "__main__":
    unittest.main()
