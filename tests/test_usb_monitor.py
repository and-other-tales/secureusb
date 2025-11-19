#!/usr/bin/env python3
"""
Unit tests for src/daemon/usb_monitor.py

Tests USB device monitoring and event handling with pyudev mocking.
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock, call

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.daemon.usb_monitor import USBDevice, USBMonitor


class TestUSBDevice(unittest.TestCase):
    """Test USBDevice class."""

    def setUp(self):
        """Set up mock pyudev device for testing."""
        self.mock_device = MagicMock()
        self.mock_device.sys_path = "/sys/bus/usb/devices/1-4"
        self.mock_device.device_type = "usb_device"
        self.mock_device.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '046d',
            'ID_MODEL_ID': 'c52b',
            'ID_VENDOR': 'Logitech',
            'ID_MODEL': 'USB_Receiver',
            'ID_SERIAL_SHORT': 'ABC123456',
            'ID_USB_INTERFACES': ':030000:030101:'
        }.get(key, default)

    @patch('pathlib.Path.exists', return_value=False)
    def test_init_basic(self, mock_exists):
        """Test basic USBDevice initialization."""
        device = USBDevice(self.mock_device)

        self.assertEqual(device.device_path, "/sys/bus/usb/devices/1-4")
        self.assertEqual(device.device_id, "1-4")
        self.assertEqual(device.vendor_id, "046d")
        self.assertEqual(device.product_id, "c52b")
        self.assertEqual(device.vendor_name, "Logitech")
        self.assertEqual(device.product_name, "USB_Receiver")
        self.assertEqual(device.serial_number, "ABC123456")

    @patch('pathlib.Path.read_text')
    @patch('pathlib.Path.exists')
    def test_read_sysfs_attributes(self, mock_exists, mock_read_text):
        """Test reading additional attributes from sysfs."""
        # Setup exists to return True for attribute files
        mock_exists.return_value = True
        mock_read_text.side_effect = [
            'Logitech, Inc.\n',  # manufacturer
            'Unifying Receiver\n',  # product
            'ABC123456\n',  # serial
            '046d\n',  # idVendor
            'c52b\n'  # idProduct
        ]

        device = USBDevice(self.mock_device)

        # Vendor name should be from pyudev, not sysfs (since ID_VENDOR was already set)
        # The _read_sysfs_attributes only fills in missing values
        self.assertIn("Logitech", device.vendor_name)

    def test_is_valid_device_true(self):
        """Test is_valid_device returns True for valid devices."""
        device = USBDevice(self.mock_device)
        self.assertTrue(device.is_valid_device())

    def test_is_valid_device_interface(self):
        """Test is_valid_device returns False for USB interfaces."""
        self.mock_device.device_type = "usb_interface"
        device = USBDevice(self.mock_device)
        self.assertFalse(device.is_valid_device())

    def test_is_valid_device_no_ids(self):
        """Test is_valid_device returns False without vendor/product IDs."""
        self.mock_device.get.side_effect = lambda key, default='': ''
        device = USBDevice(self.mock_device)
        self.assertFalse(device.is_valid_device())

    def test_get_display_name_full(self):
        """Test get_display_name with full info."""
        device = USBDevice(self.mock_device)
        name = device.get_display_name()
        self.assertEqual(name, "Logitech USB_Receiver")

    def test_get_display_name_product_only(self):
        """Test get_display_name with product only."""
        self.mock_device.get.side_effect = lambda key, default='': {
            'ID_MODEL_ID': 'c52b',
            'ID_MODEL': 'USB_Receiver',
            'ID_VENDOR_ID': '046d'
        }.get(key, default)

        device = USBDevice(self.mock_device)
        name = device.get_display_name()
        self.assertEqual(name, "USB_Receiver")

    def test_get_display_name_fallback(self):
        """Test get_display_name fallback to IDs."""
        self.mock_device.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '046d',
            'ID_MODEL_ID': 'c52b'
        }.get(key, default)

        device = USBDevice(self.mock_device)
        name = device.get_display_name()
        self.assertEqual(name, "USB Device 046d:c52b")

    def test_to_dict(self):
        """Test converting device to dictionary."""
        device = USBDevice(self.mock_device)
        device_dict = device.to_dict()

        self.assertIsInstance(device_dict, dict)
        self.assertEqual(device_dict['device_id'], "1-4")
        self.assertEqual(device_dict['vendor_id'], "046d")
        self.assertEqual(device_dict['product_id'], "c52b")
        self.assertIn('display_name', device_dict)

    def test_str_representation(self):
        """Test string representation of device."""
        device = USBDevice(self.mock_device)
        str_repr = str(device)

        self.assertIn("Logitech", str_repr)
        self.assertIn("046d:c52b", str_repr)
        self.assertIn("1-4", str_repr)


class TestUSBMonitorInit(unittest.TestCase):
    """Test USBMonitor initialization."""

    @patch('src.daemon.usb_monitor.pyudev.Monitor')
    @patch('src.daemon.usb_monitor.pyudev.Context')
    def test_init_no_callback(self, mock_context, mock_monitor):
        """Test monitor initialization without callback."""
        monitor = USBMonitor()

        self.assertIsNone(monitor.callback)
        self.assertFalse(monitor.running)
        self.assertIsNone(monitor.observer)
        mock_context.assert_called_once()

    @patch('src.daemon.usb_monitor.pyudev.Monitor')
    @patch('src.daemon.usb_monitor.pyudev.Context')
    def test_init_with_callback(self, mock_context, mock_monitor):
        """Test monitor initialization with callback."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        self.assertEqual(monitor.callback, callback)

    @patch('src.daemon.usb_monitor.pyudev.Monitor')
    @patch('src.daemon.usb_monitor.pyudev.Context')
    def test_monitor_filter_setup(self, mock_context, mock_monitor):
        """Test that monitor is configured with correct filters."""
        mock_monitor_instance = MagicMock()
        mock_monitor.from_netlink.return_value = mock_monitor_instance

        monitor = USBMonitor()

        mock_monitor.from_netlink.assert_called_once()
        mock_monitor_instance.filter_by.assert_called_once_with(
            subsystem='usb',
            device_type='usb_device'
        )


class TestUSBMonitorStartStop(unittest.TestCase):
    """Test monitor start/stop functionality."""

    def setUp(self):
        """Set up monitor with mocked dependencies."""
        self.patcher_context = patch('src.daemon.usb_monitor.pyudev.Context')
        self.patcher_monitor = patch('src.daemon.usb_monitor.pyudev.Monitor')
        self.patcher_observer = patch('src.daemon.usb_monitor.pyudev.MonitorObserver')

        self.mock_context = self.patcher_context.start()
        self.mock_monitor_class = self.patcher_monitor.start()
        self.mock_observer_class = self.patcher_observer.start()

        self.mock_monitor = MagicMock()
        self.mock_monitor_class.from_netlink.return_value = self.mock_monitor

    def tearDown(self):
        """Clean up patches."""
        self.patcher_context.stop()
        self.patcher_monitor.stop()
        self.patcher_observer.stop()

    def test_start_threaded(self):
        """Test starting monitor in threaded mode."""
        monitor = USBMonitor()
        monitor.start(threaded=True)

        self.assertTrue(monitor.running)
        self.mock_observer_class.assert_called_once()
        self.assertIsNotNone(monitor.observer)

    def test_start_already_running(self):
        """Test starting monitor when already running."""
        monitor = USBMonitor()
        monitor.running = True

        monitor.start(threaded=True)

        # Should not create new observer
        self.mock_observer_class.assert_not_called()

    def test_stop(self):
        """Test stopping monitor."""
        mock_observer = MagicMock()
        self.mock_observer_class.return_value = mock_observer

        monitor = USBMonitor()
        monitor.start(threaded=True)

        monitor.stop()

        self.assertFalse(monitor.running)
        mock_observer.stop.assert_called_once()
        self.assertIsNone(monitor.observer)

    def test_stop_not_running(self):
        """Test stopping monitor when not running."""
        monitor = USBMonitor()

        # Should not raise error
        monitor.stop()

        self.assertFalse(monitor.running)

    def test_is_running(self):
        """Test is_running method."""
        monitor = USBMonitor()

        self.assertFalse(monitor.is_running())

        monitor.running = True
        self.assertTrue(monitor.is_running())


class TestUSBMonitorEventHandling(unittest.TestCase):
    """Test USB event handling."""

    def setUp(self):
        """Set up monitor with mocked dependencies."""
        self.patcher_context = patch('src.daemon.usb_monitor.pyudev.Context')
        self.patcher_monitor = patch('src.daemon.usb_monitor.pyudev.Monitor')

        self.mock_context = self.patcher_context.start()
        self.mock_monitor_class = self.patcher_monitor.start()

        self.mock_monitor = MagicMock()
        self.mock_monitor_class.from_netlink.return_value = self.mock_monitor

        # Create mock device
        self.mock_device = MagicMock()
        self.mock_device.action = 'add'
        self.mock_device.sys_path = "/sys/bus/usb/devices/1-4"
        self.mock_device.device_type = "usb_device"
        self.mock_device.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '046d',
            'ID_MODEL_ID': 'c52b',
            'ID_VENDOR': 'Logitech',
            'ID_MODEL': 'USB_Receiver'
        }.get(key, default)

    def tearDown(self):
        """Clean up patches."""
        self.patcher_context.stop()
        self.patcher_monitor.stop()

    @patch('pathlib.Path.exists', return_value=False)
    def test_on_event_add(self, mock_exists):
        """Test handling device add event."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        monitor._on_event(self.mock_device)

        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertIsInstance(args[0], USBDevice)
        self.assertEqual(args[1], 'add')

    @patch('pathlib.Path.exists', return_value=False)
    def test_on_event_remove(self, mock_exists):
        """Test handling device remove event."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        # First add the device
        self.mock_device.action = 'add'
        monitor._on_event(self.mock_device)

        # Then remove it
        self.mock_device.action = 'remove'
        monitor._on_event(self.mock_device)

        self.assertEqual(callback.call_count, 2)
        # Check second call was remove
        args = callback.call_args[0]
        self.assertEqual(args[1], 'remove')

    @patch('pathlib.Path.exists', return_value=False)
    def test_on_event_duplicate_prevention(self, mock_exists):
        """Test that duplicate add events are filtered."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        # Send same add event twice
        monitor._on_event(self.mock_device)
        monitor._on_event(self.mock_device)

        # Callback should only be called once
        callback.assert_called_once()

    @patch('pathlib.Path.exists', return_value=False)
    def test_on_event_invalid_device_filtered(self, mock_exists):
        """Test that invalid devices are filtered out."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        # Create device without IDs (invalid)
        self.mock_device.get.side_effect = lambda key, default='': ''

        monitor._on_event(self.mock_device)

        # Callback should not be called
        callback.assert_not_called()

    def test_on_event_unsupported_action(self):
        """Test that unsupported actions are ignored."""
        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        self.mock_device.action = 'bind'
        monitor._on_event(self.mock_device)

        callback.assert_not_called()


class TestUSBMonitorScanExisting(unittest.TestCase):
    """Test scanning for existing devices."""

    def setUp(self):
        """Set up monitor with mocked dependencies."""
        self.patcher_context = patch('src.daemon.usb_monitor.pyudev.Context')
        self.patcher_monitor = patch('src.daemon.usb_monitor.pyudev.Monitor')

        self.mock_context_class = self.patcher_context.start()
        self.mock_monitor_class = self.patcher_monitor.start()

        self.mock_context = MagicMock()
        self.mock_context_class.return_value = self.mock_context

        self.mock_monitor = MagicMock()
        self.mock_monitor_class.from_netlink.return_value = self.mock_monitor

    def tearDown(self):
        """Clean up patches."""
        self.patcher_context.stop()
        self.patcher_monitor.stop()

    @patch('pathlib.Path.exists', return_value=False)
    def test_scan_existing_devices(self, mock_exists):
        """Test scanning for existing USB devices."""
        # Create mock devices
        mock_device1 = MagicMock()
        mock_device1.sys_path = "/sys/bus/usb/devices/1-4"
        mock_device1.device_type = "usb_device"
        mock_device1.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '046d',
            'ID_MODEL_ID': 'c52b'
        }.get(key, default)

        mock_device2 = MagicMock()
        mock_device2.sys_path = "/sys/bus/usb/devices/1-5"
        mock_device2.device_type = "usb_device"
        mock_device2.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '0781',
            'ID_MODEL_ID': '5583'
        }.get(key, default)

        self.mock_context.list_devices.return_value = [mock_device1, mock_device2]

        monitor = USBMonitor()
        devices = monitor.scan_existing_devices()

        self.assertEqual(len(devices), 2)
        self.assertIsInstance(devices[0], USBDevice)
        self.assertIsInstance(devices[1], USBDevice)

    @patch('pathlib.Path.exists', return_value=False)
    def test_scan_existing_filters_invalid(self, mock_exists):
        """Test that scanning filters out invalid devices."""
        # Create mock device without IDs (invalid)
        mock_device = MagicMock()
        mock_device.sys_path = "/sys/bus/usb/devices/1-4"
        mock_device.device_type = "usb_device"
        mock_device.get.side_effect = lambda key, default='': ''

        self.mock_context.list_devices.return_value = [mock_device]

        monitor = USBMonitor()
        devices = monitor.scan_existing_devices()

        self.assertEqual(len(devices), 0)

    def test_scan_existing_empty(self):
        """Test scanning when no devices present."""
        self.mock_context.list_devices.return_value = []

        monitor = USBMonitor()
        devices = monitor.scan_existing_devices()

        self.assertEqual(len(devices), 0)


class TestUSBMonitorEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    @patch('src.daemon.usb_monitor.pyudev.Monitor')
    @patch('src.daemon.usb_monitor.pyudev.Context')
    def test_callback_exception_handling(self, mock_context, mock_monitor_class):
        """Test that exceptions in callback don't crash monitor."""
        mock_monitor = MagicMock()
        mock_monitor_class.from_netlink.return_value = mock_monitor

        # Create callback that raises exception
        callback = MagicMock(side_effect=Exception("Test error"))
        monitor = USBMonitor(callback=callback)

        # Create mock device
        mock_device = MagicMock()
        mock_device.action = 'add'
        mock_device.sys_path = "/sys/bus/usb/devices/1-4"
        mock_device.device_type = "usb_device"
        mock_device.get.side_effect = lambda key, default='': {
            'ID_VENDOR_ID': '046d',
            'ID_MODEL_ID': 'c52b'
        }.get(key, default)

        # Should not raise exception
        with patch('pathlib.Path.exists', return_value=False):
            monitor._on_event(mock_device)

    @patch('src.daemon.usb_monitor.pyudev.Monitor')
    @patch('src.daemon.usb_monitor.pyudev.Context')
    def test_device_creation_exception(self, mock_context, mock_monitor_class):
        """Test handling of device creation exceptions."""
        mock_monitor = MagicMock()
        mock_monitor_class.from_netlink.return_value = mock_monitor

        callback = MagicMock()
        monitor = USBMonitor(callback=callback)

        # Create device that will cause exception
        mock_device = MagicMock()
        mock_device.action = 'add'
        mock_device.sys_path = None  # Will cause error

        # Should not crash
        monitor._on_event(mock_device)

        # Callback should not be called
        callback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
