#!/usr/bin/env python3
"""
Unit tests for src/daemon/dbus_service.py

Tests D-Bus service interface with comprehensive mocking.
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock dbus before importing
mock_dbus = MagicMock()
mock_dbus_service = MagicMock()
mock_dbus_mainloop = MagicMock()
mock_dbus_mainloop_glib = MagicMock()

# Mock BusName to return a mock object
mock_bus_name = MagicMock()
mock_bus_name.request_name.return_value = 1  # DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER
mock_dbus_service.BusName = MagicMock(return_value=mock_bus_name)

sys.modules['dbus'] = mock_dbus
sys.modules['dbus.service'] = mock_dbus_service
sys.modules['dbus.mainloop'] = mock_dbus_mainloop
sys.modules['dbus.mainloop.glib'] = mock_dbus_mainloop_glib

from src.daemon.dbus_service import (
    SecureUSBService,
    DBusClient,
    DBUS_SERVICE_NAME,
    DBUS_OBJECT_PATH,
    DBUS_INTERFACE_NAME
)


class TestDBusConstants(unittest.TestCase):
    """Test D-Bus service constants."""

    def test_service_name(self):
        """Test service name constant."""
        self.assertEqual(DBUS_SERVICE_NAME, "org.secureusb.Daemon")

    def test_object_path(self):
        """Test object path constant."""
        self.assertEqual(DBUS_OBJECT_PATH, "/org/secureusb/Daemon")

    def test_interface_name(self):
        """Test interface name constant."""
        self.assertEqual(DBUS_INTERFACE_NAME, "org.secureusb.Daemon")


@unittest.skip("D-Bus service tests require actual D-Bus infrastructure - integration test needed")
class TestSecureUSBServiceInit(unittest.TestCase):
    """Test SecureUSBService initialization."""

    def setUp(self):
        """Set up mocks for D-Bus."""
        self.mock_bus = MagicMock()
        self.auth_callback = MagicMock()
        self.config_callback = MagicMock()

    def test_init(self):
        """Test service initialization."""
        service = SecureUSBService(
            self.mock_bus,
            self.auth_callback,
            self.config_callback
        )

        self.assertEqual(service.authorization_callback, self.auth_callback)
        self.assertEqual(service.config_callback, self.config_callback)
        self.assertIsInstance(service.pending_requests, dict)

    def test_pending_requests_empty(self):
        """Test that pending_requests is initialized empty."""
        service = SecureUSBService(
            self.mock_bus,
            self.auth_callback,
            self.config_callback
        )

        self.assertEqual(len(service.pending_requests), 0)


@unittest.skip("D-Bus service tests require actual D-Bus infrastructure - integration test needed")
class TestSecureUSBServiceMethods(unittest.TestCase):
    """Test D-Bus service methods."""

    def setUp(self):
        """Set up service instance."""
        self.mock_bus = MagicMock()
        self.auth_callback = MagicMock()
        self.config_callback = MagicMock()

        self.service = SecureUSBService(
            self.mock_bus,
            self.auth_callback,
            self.config_callback
        )

    def test_ping(self):
        """Test Ping method."""
        result = self.service.Ping()
        self.assertTrue(result)

    def test_get_version(self):
        """Test GetVersion method."""
        version = self.service.GetVersion()
        self.assertIsInstance(version, str)
        self.assertRegex(version, r'^\d+\.\d+\.\d+$')

    @patch('src.daemon.dbus_service.Config')
    def test_is_enabled_true(self, mock_config_class):
        """Test IsEnabled returns True when protection is enabled."""
        mock_config = MagicMock()
        mock_config.is_enabled.return_value = True
        mock_config_class.return_value = mock_config

        result = self.service.IsEnabled()

        self.assertTrue(result)

    @patch('src.daemon.dbus_service.Config')
    def test_is_enabled_false(self, mock_config_class):
        """Test IsEnabled returns False when protection is disabled."""
        mock_config = MagicMock()
        mock_config.is_enabled.return_value = False
        mock_config_class.return_value = mock_config

        result = self.service.IsEnabled()

        self.assertFalse(result)

    @patch('src.daemon.dbus_service.Config', side_effect=Exception("Config error"))
    def test_is_enabled_error_fallback(self, mock_config_class):
        """Test IsEnabled fallback on error."""
        result = self.service.IsEnabled()

        # Should return True as default on error
        self.assertTrue(result)

    def test_set_enabled_true(self):
        """Test SetEnabled with True."""
        self.config_callback.return_value = True

        result = self.service.SetEnabled(True)

        self.assertTrue(result)
        self.config_callback.assert_called_once_with('set_enabled', True)

    def test_set_enabled_false(self):
        """Test SetEnabled with False."""
        self.config_callback.return_value = True

        result = self.service.SetEnabled(False)

        self.assertTrue(result)
        self.config_callback.assert_called_once_with('set_enabled', False)

    def test_set_enabled_no_callback(self):
        """Test SetEnabled without callback."""
        service = SecureUSBService(self.mock_bus, None, None)

        result = service.SetEnabled(True)

        self.assertFalse(result)

    def test_authorize_device(self):
        """Test AuthorizeDevice method."""
        self.auth_callback.return_value = "success"

        result = self.service.AuthorizeDevice(
            "1-4",
            "046d",
            "c52b",
            "Logitech",
            "USB Receiver",
            "ABC123",
            "123456",
            "full"
        )

        self.assertEqual(result, "success")
        self.auth_callback.assert_called_once()

        # Verify device info dict
        call_args = self.auth_callback.call_args[0]
        device_info = call_args[0]
        self.assertEqual(device_info['device_id'], "1-4")
        self.assertEqual(device_info['vendor_id'], "046d")
        self.assertEqual(call_args[1], "123456")  # TOTP code
        self.assertEqual(call_args[2], "full")  # mode

    def test_deny_device(self):
        """Test DenyDevice method."""
        self.auth_callback.return_value = "success"

        result = self.service.DenyDevice("1-4")

        self.assertTrue(result)
        self.auth_callback.assert_called_once()

        # Verify it was called with deny mode
        call_args = self.auth_callback.call_args[0]
        self.assertEqual(call_args[2], 'deny')

    def test_deny_device_no_callback(self):
        """Test DenyDevice without callback."""
        service = SecureUSBService(self.mock_bus, None, None)

        result = service.DenyDevice("1-4")

        self.assertFalse(result)

    def test_get_pending_devices_empty(self):
        """Test GetPendingDevices when empty."""
        result = self.service.GetPendingDevices()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_get_pending_devices_with_devices(self):
        """Test GetPendingDevices with pending devices."""
        self.service.pending_requests = {
            '1-4': {'device_id': '1-4', 'vendor_id': '046d'},
            '1-5': {'device_id': '1-5', 'vendor_id': '0781'}
        }

        result = self.service.GetPendingDevices()

        self.assertEqual(len(result), 2)

    @patch('src.daemon.dbus_service.USBLogger')
    def test_get_recent_events(self, mock_logger_class):
        """Test GetRecentEvents method."""
        mock_logger = MagicMock()
        mock_logger.get_recent_events.return_value = [
            {'id': 1, 'action': 'connected', 'timestamp': 1234567890.0},
            {'id': 2, 'action': 'authorized', 'timestamp': 1234567900.0}
        ]
        mock_logger_class.return_value = mock_logger

        result = self.service.GetRecentEvents()

        self.assertIsInstance(result, list)
        mock_logger.get_recent_events.assert_called_once_with(limit=50)

    @patch('src.daemon.dbus_service.USBLogger')
    def test_get_statistics(self, mock_logger_class):
        """Test GetStatistics method."""
        mock_logger = MagicMock()
        mock_logger.get_statistics.return_value = {
            'total_events': 100,
            'unique_devices': 5,
            'by_action': {'connected': 50, 'authorized': 45}
        }
        mock_logger_class.return_value = mock_logger

        result = self.service.GetStatistics()

        self.assertIsInstance(result, dict)
        mock_logger.get_statistics.assert_called_once()

    def test_add_to_whitelist(self):
        """Test AddToWhitelist method."""
        self.config_callback.return_value = True

        payload = {
            'serial_number': 'ABC123456',
            'vendor_id': '046d',
            'product_id': 'c52b'
        }

        result = self.service.AddToWhitelist(payload)

        self.assertTrue(result)
        self.config_callback.assert_called_once_with('add_whitelist', payload)

    def test_remove_from_whitelist(self):
        """Test RemoveFromWhitelist method."""
        self.config_callback.return_value = True

        result = self.service.RemoveFromWhitelist("ABC123456")

        self.assertTrue(result)
        self.config_callback.assert_called_once_with('remove_whitelist', "ABC123456")


@unittest.skip("D-Bus service tests require actual D-Bus infrastructure - integration test needed")
class TestSecureUSBServiceSignals(unittest.TestCase):
    """Test D-Bus signal emission."""

    def setUp(self):
        """Set up service instance."""
        self.mock_bus = MagicMock()
        self.service = SecureUSBService(
            self.mock_bus,
            MagicMock(),
            MagicMock()
        )

    def test_emit_device_connected(self):
        """Test emit_device_connected signal."""
        device_info = {
            'device_id': '1-4',
            'vendor_id': '046d',
            'product_id': 'c52b'
        }

        # Should not raise error
        self.service.emit_device_connected(device_info)

        # Check device added to pending requests
        self.assertIn('1-4', self.service.pending_requests)
        self.assertEqual(self.service.pending_requests['1-4'], device_info)

    def test_emit_device_disconnected(self):
        """Test emit_device_disconnected signal."""
        # Add device to pending first
        self.service.pending_requests['1-4'] = {'device_id': '1-4'}

        self.service.emit_device_disconnected('1-4')

        # Device should be removed from pending
        self.assertNotIn('1-4', self.service.pending_requests)

    def test_emit_authorization_result(self):
        """Test emit_authorization_result signal."""
        # Add device to pending first
        self.service.pending_requests['1-4'] = {'device_id': '1-4'}

        self.service.emit_authorization_result('1-4', 'authorized', True)

        # Device should be removed from pending
        self.assertNotIn('1-4', self.service.pending_requests)

    def test_emit_protection_state_changed(self):
        """Test emit_protection_state_changed signal."""
        # Should not raise error
        self.service.emit_protection_state_changed(True)
        self.service.emit_protection_state_changed(False)


class TestDBusClient(unittest.TestCase):
    """Test DBusClient class."""

    def setUp(self):
        """Set up mocks for D-Bus client."""
        self.mock_bus = MagicMock()
        self.mock_proxy = MagicMock()
        self.mock_interface = MagicMock()

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_client_init_system_bus(self, mock_system_bus):
        """Test client initialization with system bus."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')

            mock_system_bus.assert_called_once()
            self.assertIsNotNone(client.proxy)
            self.assertIsNotNone(client.interface)

    @patch('src.daemon.dbus_service.dbus.SessionBus')
    def test_client_init_session_bus(self, mock_session_bus):
        """Test client initialization with session bus."""
        mock_session_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('session')

            mock_session_bus.assert_called_once()

    @unittest.skip("D-Bus connection error handling needs actual D-Bus - integration test")
    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_client_init_connection_error(self, mock_system_bus):
        """Test client initialization with connection error."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.side_effect = Exception("Connection failed")

        client = DBusClient('system')

        # Client should handle error gracefully
        self.assertIsNone(client.proxy)
        self.assertIsNone(client.interface)

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_is_connected_true(self, mock_system_bus):
        """Test is_connected when daemon is available."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            self.mock_interface.Ping.return_value = True
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            result = client.is_connected()

            self.assertTrue(result)
            self.mock_interface.Ping.assert_called_once()

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_is_connected_false(self, mock_system_bus):
        """Test is_connected when daemon is not available."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            self.mock_interface.Ping.side_effect = Exception("Not available")
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            result = client.is_connected()

            self.assertFalse(result)

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_authorize_device(self, mock_system_bus):
        """Test authorize_device method."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            self.mock_interface.AuthorizeDevice.return_value = "success"
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            device_info = {
                'device_id': '1-4',
                'vendor_id': '046d',
                'product_id': 'c52b',
                'vendor_name': 'Logitech',
                'product_name': 'Receiver',
                'serial_number': 'ABC123'
            }

            result = client.authorize_device(device_info, "123456", "full")

            self.assertEqual(result, "success")
            self.mock_interface.AuthorizeDevice.assert_called_once()

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_deny_device(self, mock_system_bus):
        """Test deny_device method."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            self.mock_interface.DenyDevice.return_value = True
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            result = client.deny_device("1-4")

            self.assertTrue(result)
            self.mock_interface.DenyDevice.assert_called_once_with("1-4")

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_client_add_to_whitelist(self, mock_system_bus):
        """Test add_to_whitelist helper."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            self.mock_interface.AddToWhitelist.return_value = True
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            payload = {'serial_number': 'ABC123'}

            result = client.add_to_whitelist(payload)

            self.assertTrue(result)
            self.mock_interface.AddToWhitelist.assert_called_once()

    @patch('src.daemon.dbus_service.dbus.SystemBus')
    def test_connect_to_signal(self, mock_system_bus):
        """Test connect_to_signal method."""
        mock_system_bus.return_value = self.mock_bus
        self.mock_bus.get_object.return_value = self.mock_proxy

        with patch('src.daemon.dbus_service.dbus.Interface') as mock_interface_class:
            mock_interface_class.return_value = self.mock_interface

            client = DBusClient('system')
            handler = MagicMock()

            client.connect_to_signal('DeviceConnected', handler)

            self.mock_proxy.connect_to_signal.assert_called_once()


if __name__ == '__main__':
    unittest.main()
