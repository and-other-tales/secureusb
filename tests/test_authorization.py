#!/usr/bin/env python3
"""
Unit tests for src/daemon/authorization.py

Tests kernel-level USB device authorization through sysfs mocking.
"""

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.daemon.authorization import USBAuthorization, AuthorizationMode


class TestUSBAuthorizationBasics(unittest.TestCase):
    """Test basic authorization class functionality."""

    @patch('os.geteuid')
    def test_is_root_true(self, mock_geteuid):
        """Test is_root returns True when UID is 0."""
        mock_geteuid.return_value = 0
        self.assertTrue(USBAuthorization.is_root())

    @patch('os.geteuid')
    def test_is_root_false(self, mock_geteuid):
        """Test is_root returns False when UID is not 0."""
        mock_geteuid.return_value = 1000
        self.assertFalse(USBAuthorization.is_root())

    def test_get_device_path_valid(self):
        """Test get_device_path with valid device ID."""
        device_id = "1-4"
        path = USBAuthorization.get_device_path(device_id)
        self.assertEqual(path, Path("/sys/bus/usb/devices/1-4"))

    def test_get_device_path_with_colon(self):
        """Test get_device_path with interface notation."""
        device_id = "1-4:1.0"
        path = USBAuthorization.get_device_path(device_id)
        self.assertEqual(path, Path("/sys/bus/usb/devices/1-4:1.0"))

    def test_get_device_path_invalid_characters(self):
        """Test get_device_path rejects path traversal attempts."""
        device_id = "../../../etc/passwd"
        with self.assertRaises(ValueError):
            USBAuthorization.get_device_path(device_id)

    def test_get_device_path_with_slash(self):
        """Test get_device_path rejects slashes."""
        device_id = "1-4/authorized"
        with self.assertRaises(ValueError):
            USBAuthorization.get_device_path(device_id)


class TestUSBAuthorizationDeviceExists(unittest.TestCase):
    """Test device existence checking."""

    def test_device_exists_true(self):
        """Test device_exists returns True when device exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()

                result = USBAuthorization.device_exists(device_id)
                self.assertTrue(result)

    def test_device_exists_false(self):
        """Test device_exists returns False when device doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "nonexistent"

                result = USBAuthorization.device_exists(device_id)
                self.assertFalse(result)


class TestUSBAuthorizationModes(unittest.TestCase):
    """Test authorization mode enum."""

    def test_authorization_modes_exist(self):
        """Test that all authorization modes are defined."""
        self.assertEqual(AuthorizationMode.FULL_ACCESS.value, "1")
        self.assertEqual(AuthorizationMode.BLOCKED.value, "0")
        self.assertEqual(AuthorizationMode.POWER_ONLY.value, "0")

    def test_blocked_and_power_only_same(self):
        """Test that BLOCKED and POWER_ONLY have same kernel value."""
        self.assertEqual(
            AuthorizationMode.BLOCKED.value,
            AuthorizationMode.POWER_ONLY.value
        )


class TestUSBAuthorizationAuthorizeDevice(unittest.TestCase):
    """Test device authorization functionality."""

    @patch('os.geteuid')
    def test_authorize_device_not_root(self, mock_geteuid):
        """Test authorize_device fails when not root."""
        mock_geteuid.return_value = 1000
        result = USBAuthorization.authorize_device("1-4", AuthorizationMode.FULL_ACCESS)
        self.assertFalse(result)

    @patch('os.geteuid')
    @patch('builtins.open', new_callable=mock_open)
    def test_authorize_device_success(self, mock_file, mock_geteuid):
        """Test successful device authorization."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.authorize_device(device_id, AuthorizationMode.FULL_ACCESS)
                self.assertTrue(result)
                mock_file.assert_called_with(authorized_file, 'w')
                mock_file().write.assert_called_with("1")

    @patch('os.geteuid')
    def test_authorize_device_file_not_found(self, mock_geteuid):
        """Test authorize_device when device file doesn't exist."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "nonexistent"

                result = USBAuthorization.authorize_device(device_id, AuthorizationMode.FULL_ACCESS)
                self.assertFalse(result)

    @patch('os.geteuid')
    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_authorize_device_permission_error(self, mock_file, mock_geteuid):
        """Test authorize_device handles permission errors."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.authorize_device(device_id, AuthorizationMode.FULL_ACCESS)
                self.assertFalse(result)


class TestUSBAuthorizationGetStatus(unittest.TestCase):
    """Test getting device authorization status."""

    @patch('builtins.open', new_callable=mock_open, read_data="1\n")
    def test_get_authorization_status_authorized(self, mock_file):
        """Test get_authorization_status when device is authorized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.get_authorization_status(device_id)
                self.assertTrue(result)

    @patch('builtins.open', new_callable=mock_open, read_data="0\n")
    def test_get_authorization_status_blocked(self, mock_file):
        """Test get_authorization_status when device is blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.get_authorization_status(device_id)
                self.assertFalse(result)

    def test_get_authorization_status_file_not_found(self):
        """Test get_authorization_status when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "nonexistent"

                result = USBAuthorization.get_authorization_status(device_id)
                self.assertIsNone(result)


class TestUSBAuthorizationBlockAllow(unittest.TestCase):
    """Test block_device and allow_device convenience methods."""

    @patch('os.geteuid')
    @patch('builtins.open', new_callable=mock_open)
    def test_block_device(self, mock_file, mock_geteuid):
        """Test block_device method."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.block_device(device_id)
                self.assertTrue(result)
                mock_file().write.assert_called_with("0")

    @patch('os.geteuid')
    @patch('builtins.open', new_callable=mock_open)
    def test_allow_device(self, mock_file, mock_geteuid):
        """Test allow_device method."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                authorized_file = device_path / "authorized"
                authorized_file.touch()

                result = USBAuthorization.allow_device(device_id)
                self.assertTrue(result)
                mock_file().write.assert_called_with("1")


class TestUSBAuthorizationReadAttribute(unittest.TestCase):
    """Test reading device attributes."""

    @patch('builtins.open', new_callable=mock_open, read_data="046d\n")
    def test_read_device_attribute_exists(self, mock_file):
        """Test reading existing device attribute."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()
                attr_file = device_path / "idVendor"
                attr_file.touch()

                result = USBAuthorization.read_device_attribute(device_id, "idVendor")
                self.assertEqual(result, "046d")

    def test_read_device_attribute_not_exists(self):
        """Test reading non-existent device attribute."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()

                result = USBAuthorization.read_device_attribute(device_id, "nonexistent")
                self.assertIsNone(result)


class TestUSBAuthorizationGetDeviceInfo(unittest.TestCase):
    """Test getting complete device information."""

    @patch('builtins.open', new_callable=mock_open)
    def test_get_device_info_success(self, mock_file):
        """Test getting device info with all attributes."""
        # Setup mock file reads
        mock_file.side_effect = [
            mock_open(read_data="046d\n").return_value,  # idVendor
            mock_open(read_data="c52b\n").return_value,  # idProduct
            mock_open(read_data="Logitech\n").return_value,  # manufacturer
            mock_open(read_data="USB Receiver\n").return_value,  # product
            mock_open(read_data="ABC123\n").return_value,  # serial
            mock_open(read_data="480\n").return_value,  # speed
            mock_open(read_data="1\n").return_value,  # authorized
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                device_id = "1-4"
                device_path = Path(temp_dir) / device_id
                device_path.mkdir()

                # Create all attribute files
                for attr in ['idVendor', 'idProduct', 'manufacturer', 'product', 'serial', 'speed', 'authorized']:
                    (device_path / attr).touch()

                result = USBAuthorization.get_device_info(device_id)

                self.assertIsNotNone(result)
                self.assertEqual(result['device_id'], device_id)
                self.assertEqual(result['vendor_id'], "046d")
                self.assertEqual(result['product_id'], "c52b")

    def test_get_device_info_nonexistent_device(self):
        """Test get_device_info with non-existent device."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                result = USBAuthorization.get_device_info("nonexistent")
                self.assertIsNone(result)


class TestUSBAuthorizationSetDefault(unittest.TestCase):
    """Test setting default authorization mode."""

    @patch('os.geteuid')
    def test_set_default_authorization_not_root(self, mock_geteuid):
        """Test set_default_authorization fails when not root."""
        mock_geteuid.return_value = 1000
        result = USBAuthorization.set_default_authorization("0")
        self.assertFalse(result)

    @patch('os.geteuid')
    @patch('builtins.open', new_callable=mock_open)
    def test_set_default_authorization_success(self, mock_file, mock_geteuid):
        """Test successful default authorization setting."""
        mock_geteuid.return_value = 0

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.daemon.authorization.USBAuthorization.USB_DEVICES_PATH', Path(temp_dir)):
                # Create USB controller directories
                for i in range(1, 3):
                    controller_path = Path(temp_dir) / f"usb{i}"
                    controller_path.mkdir()
                    authorized_default = controller_path / "authorized_default"
                    authorized_default.touch()

                result = USBAuthorization.set_default_authorization("0")
                self.assertTrue(result)

                # Verify it was called for each controller
                self.assertEqual(mock_file.call_count, 2)


if __name__ == '__main__':
    unittest.main()
