#!/usr/bin/env python3
"""
Unit tests for windows/src/usb_monitor.py

Exercises the WindowsUSBMonitor helpers to ensure cross-platform behaviour
can be validated on the Linux build agents.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from windows.src.usb_monitor import WindowsUSBMonitor  # noqa: E402


class TestWindowsUSBMonitorHelpers(unittest.TestCase):
    """Validate helper methods that parse PowerShell output."""

    def test_extract_ids_and_serial(self):
        """VID/PID parsing should be case-insensitive."""
        instance = "USB\\VID_1A2B&PID_C3D4\\SN123456"
        vendor, product = WindowsUSBMonitor._extract_ids(instance)
        self.assertEqual(vendor, "1a2b")
        self.assertEqual(product, "c3d4")
        self.assertEqual(WindowsUSBMonitor._extract_serial(instance), "SN123456")

    def test_extract_ids_missing_tokens(self):
        """Missing VID/PID should fall back to empty strings."""
        vendor, product = WindowsUSBMonitor._extract_ids("USB\\UNKNOWN")
        self.assertEqual(vendor, "")
        self.assertEqual(product, "")
        self.assertEqual(WindowsUSBMonitor._extract_serial("NO_BACKSLASH"), "")

    @patch('windows.src.usb_monitor.subprocess.run', side_effect=FileNotFoundError)
    def test_enumerate_devices_handles_missing_powershell(self, _mock_run):
        """Gracefully handle systems without PowerShell."""
        monitor = WindowsUSBMonitor()
        self.assertEqual(monitor._enumerate_devices(), {})

    @patch('windows.src.usb_monitor.subprocess.run')
    def test_enumerate_devices_parses_json_payload(self, mock_run):
        """Ensure JSON listing converts into WindowsUSBDevice objects."""
        payload = [{
            "InstanceId": "USB\\VID_1234&PID_ABCD\\SER987",
            "FriendlyName": "SecureUSB Test Device",
            "Status": "OK",
        }]
        mock_run.return_value = SimpleNamespace(stdout=json.dumps(payload), returncode=0)

        monitor = WindowsUSBMonitor()
        devices = monitor._enumerate_devices()

        self.assertEqual(len(devices), 1)
        parsed = devices["USB\\VID_1234&PID_ABCD\\SER987"]
        self.assertEqual(parsed.vendor_id, "1234")
        self.assertEqual(parsed.product_id, "abcd")
        self.assertEqual(parsed.serial_number, "SER987")
        self.assertEqual(parsed.friendly_name, "SecureUSB Test Device")


if __name__ == '__main__':
    unittest.main()
