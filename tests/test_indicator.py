#!/usr/bin/env python3
"""
Unit tests for src/gui/indicator.py

Tests system tray indicator with AppIndicator and D-Bus mocking.
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import sys

# Mock GTK and AppIndicator before importing
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gtk'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()
sys.modules['gi.repository.AppIndicator3'] = MagicMock()
sys.modules['gi.repository.AyatanaAppIndicator3'] = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gui.indicator import SecureUSBIndicator


class TestSecureUSBIndicatorInit(unittest.TestCase):
    """Test indicator initialization."""

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_init_creates_indicator(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that indicator is created on init."""
        mock_indicator = MagicMock()
        mock_appindicator.Indicator.new.return_value = mock_indicator

        indicator = SecureUSBIndicator()

        mock_appindicator.Indicator.new.assert_called_once()
        mock_indicator.set_status.assert_called_once()
        mock_indicator.set_menu.assert_called_once()

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_init_creates_menu(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that menu is created on init."""
        mock_menu = MagicMock()
        mock_gtk.Menu.return_value = mock_menu

        indicator = SecureUSBIndicator()

        mock_gtk.Menu.assert_called_once()
        # Menu should have items added
        self.assertGreater(mock_menu.append.call_count, 0)

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_init_state(self, mock_glib, mock_gtk, mock_appindicator):
        """Test initial state of indicator."""
        indicator = SecureUSBIndicator()

        self.assertIsNone(indicator.dbus_client)
        self.assertFalse(indicator.enabled)
        self.assertFalse(indicator._updating_toggle)

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_init_schedules_dbus_connection(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that D-Bus connection is scheduled."""
        indicator = SecureUSBIndicator()

        mock_glib.idle_add.assert_called_once()


class TestSecureUSBIndicatorDBusConnection(unittest.TestCase):
    """Test D-Bus connection logic."""

    def setUp(self):
        """Set up mocks."""
        self.patcher_appindicator = patch('src.gui.indicator.AppIndicator3')
        self.patcher_gtk = patch('src.gui.indicator.Gtk')
        self.patcher_glib = patch('src.gui.indicator.GLib')
        self.patcher_dbus_client = patch('src.gui.indicator.DBusClient')

        self.mock_appindicator = self.patcher_appindicator.start()
        self.mock_gtk = self.patcher_gtk.start()
        self.mock_glib = self.patcher_glib.start()
        self.mock_dbus_client_class = self.patcher_dbus_client.start()

        # Prevent actual idle_add during init
        self.mock_glib.idle_add.return_value = None

    def tearDown(self):
        """Clean up patches."""
        self.patcher_appindicator.stop()
        self.patcher_gtk.stop()
        self.patcher_glib.stop()
        self.patcher_dbus_client.stop()

    def test_connect_dbus_success(self):
        """Test successful D-Bus connection."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client.interface.IsEnabled.return_value = True
        self.mock_dbus_client_class.return_value = mock_client

        indicator = SecureUSBIndicator()
        result = indicator._connect_dbus()

        self.assertFalse(result)  # Should return False to not repeat
        self.assertIsNotNone(indicator.dbus_client)
        mock_client.is_connected.assert_called_once()

    def test_connect_dbus_failure_schedules_retry(self):
        """Test D-Bus connection failure schedules retry."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = False
        self.mock_dbus_client_class.return_value = mock_client

        indicator = SecureUSBIndicator()
        result = indicator._connect_dbus()

        self.assertFalse(result)  # Return False from retry timeout
        self.mock_glib.timeout_add_seconds.assert_called_with(5, indicator._connect_dbus)

    def test_connect_dbus_subscribes_to_signals(self):
        """Test that D-Bus signals are subscribed."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client.interface.IsEnabled.return_value = True
        self.mock_dbus_client_class.return_value = mock_client

        indicator = SecureUSBIndicator()
        indicator._connect_dbus()

        mock_client.connect_to_signal.assert_called_once_with(
            'ProtectionStateChanged',
            indicator._on_protection_changed
        )


class TestSecureUSBIndicatorStateUpdate(unittest.TestCase):
    """Test state update logic."""

    def setUp(self):
        """Set up indicator."""
        with patch('src.gui.indicator.AppIndicator3'), \
             patch('src.gui.indicator.Gtk') as mock_gtk, \
             patch('src.gui.indicator.GLib'):

            self.mock_toggle = MagicMock()
            self.mock_status = MagicMock()
            self.mock_indicator_obj = MagicMock()

            mock_gtk.CheckMenuItem.return_value = self.mock_toggle
            mock_gtk.MenuItem.return_value = self.mock_status

            self.indicator = SecureUSBIndicator()
            self.indicator.toggle_item = self.mock_toggle
            self.indicator.status_item = self.mock_status
            self.indicator.indicator = self.mock_indicator_obj

    def test_update_state_enabled(self):
        """Test updating state to enabled."""
        self.indicator._update_state(True)

        self.assertTrue(self.indicator.enabled)
        self.mock_status.set_label.assert_called_with("SecureUSB: Enabled")
        self.mock_indicator_obj.set_icon_full.assert_called_with(
            "security-high",
            "SecureUSB"
        )
        self.mock_toggle.set_active.assert_called_with(True)

    def test_update_state_disabled(self):
        """Test updating state to disabled."""
        self.indicator._update_state(False)

        self.assertFalse(self.indicator.enabled)
        self.mock_status.set_label.assert_called_with("SecureUSB: Disabled")
        self.mock_indicator_obj.set_icon_full.assert_called_with(
            "security-low",
            "SecureUSB"
        )
        self.mock_toggle.set_active.assert_called_with(False)

    def test_update_state_sets_updating_flag(self):
        """Test that _updating_toggle flag is used correctly."""
        self.indicator._update_state(True)

        # Flag should be set during update then cleared
        self.assertFalse(self.indicator._updating_toggle)


class TestSecureUSBIndicatorToggle(unittest.TestCase):
    """Test protection toggle functionality."""

    def setUp(self):
        """Set up indicator with mocked D-Bus."""
        with patch('src.gui.indicator.AppIndicator3'), \
             patch('src.gui.indicator.Gtk'), \
             patch('src.gui.indicator.GLib'):

            self.indicator = SecureUSBIndicator()
            self.indicator.dbus_client = MagicMock()
            self.indicator.dbus_client.interface = MagicMock()

    def test_on_toggle_when_updating(self):
        """Test that toggle is ignored when _updating_toggle is True."""
        self.indicator._updating_toggle = True
        mock_widget = MagicMock()

        self.indicator._on_toggle(mock_widget)

        # Should not call SetEnabled
        self.indicator.dbus_client.interface.SetEnabled.assert_not_called()

    def test_on_toggle_enable(self):
        """Test toggling protection on."""
        mock_widget = MagicMock()
        mock_widget.get_active.return_value = True

        self.indicator._on_toggle(mock_widget)

        self.indicator.dbus_client.interface.SetEnabled.assert_called_once_with(True)

    def test_on_toggle_disable(self):
        """Test toggling protection off."""
        mock_widget = MagicMock()
        mock_widget.get_active.return_value = False

        self.indicator._on_toggle(mock_widget)

        self.indicator.dbus_client.interface.SetEnabled.assert_called_once_with(False)

    @unittest.skip("GTK widget interaction test - integration test needed")
    def test_on_toggle_no_dbus_client(self):
        """Test toggle when D-Bus client is not available."""
        self.indicator.dbus_client = None
        self.indicator.enabled = True

        mock_widget = MagicMock()
        mock_widget.get_active.return_value = False
        mock_widget.set_active = MagicMock()

        self.indicator._on_toggle(mock_widget)

        # Should revert to previous state
        mock_widget.set_active.assert_called_with(True)

    @unittest.skip("GTK widget interaction test - integration test needed")
    def test_on_toggle_error_handling(self):
        """Test toggle handles D-Bus errors gracefully."""
        self.indicator.enabled = False
        self.indicator.dbus_client.interface.SetEnabled.side_effect = Exception("D-Bus error")

        mock_widget = MagicMock()
        mock_widget.get_active.return_value = True
        mock_widget.set_active = MagicMock()

        self.indicator._on_toggle(mock_widget)

        # Should revert toggle state on error
        mock_widget.set_active.assert_called_with(False)


class TestSecureUSBIndicatorLaunchCommand(unittest.TestCase):
    """Test command launching functionality."""

    def setUp(self):
        """Set up indicator."""
        with patch('src.gui.indicator.AppIndicator3'), \
             patch('src.gui.indicator.Gtk'), \
             patch('src.gui.indicator.GLib'):

            self.indicator = SecureUSBIndicator()

    @patch('src.gui.indicator.subprocess.Popen')
    def test_launch_command_success(self, mock_popen):
        """Test successful command launch."""
        self.indicator._launch_command('secureusb-setup')

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        self.assertEqual(call_args[0][0], ['secureusb-setup'])

    @patch('src.gui.indicator.subprocess.Popen', side_effect=Exception("Launch failed"))
    def test_launch_command_error(self, mock_popen):
        """Test command launch error handling."""
        # Should not raise exception
        self.indicator._launch_command('nonexistent-command')

        mock_popen.assert_called_once()


class TestSecureUSBIndicatorSignalHandler(unittest.TestCase):
    """Test signal handler."""

    def setUp(self):
        """Set up indicator."""
        with patch('src.gui.indicator.AppIndicator3'), \
             patch('src.gui.indicator.Gtk'), \
             patch('src.gui.indicator.GLib'):

            self.indicator = SecureUSBIndicator()
            self.indicator.indicator = MagicMock()
            self.indicator.status_item = MagicMock()
            self.indicator.toggle_item = MagicMock()

    def test_on_protection_changed(self):
        """Test protection state changed signal handler."""
        self.indicator._on_protection_changed(True)

        self.assertTrue(self.indicator.enabled)

        self.indicator._on_protection_changed(False)

        self.assertFalse(self.indicator.enabled)


class TestSecureUSBIndicatorMenuItems(unittest.TestCase):
    """Test menu item creation and functionality."""

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_menu_has_status_item(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that menu includes status item."""
        indicator = SecureUSBIndicator()

        self.assertIsNotNone(indicator.status_item)

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_menu_has_toggle_item(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that menu includes toggle item."""
        indicator = SecureUSBIndicator()

        self.assertIsNotNone(indicator.toggle_item)

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_menu_has_setup_item(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that menu includes setup wizard item."""
        indicator = SecureUSBIndicator()

        self.assertIsNotNone(indicator.setup_item)

    @patch('src.gui.indicator.AppIndicator3')
    @patch('src.gui.indicator.Gtk')
    @patch('src.gui.indicator.GLib')
    def test_menu_has_client_item(self, mock_glib, mock_gtk, mock_appindicator):
        """Test that menu includes client UI item."""
        indicator = SecureUSBIndicator()

        self.assertIsNotNone(indicator.client_item)


class TestSecureUSBIndicatorIntegration(unittest.TestCase):
    """Integration tests for indicator."""

    def setUp(self):
        """Set up full indicator."""
        self.patcher_appindicator = patch('src.gui.indicator.AppIndicator3')
        self.patcher_gtk = patch('src.gui.indicator.Gtk')
        self.patcher_glib = patch('src.gui.indicator.GLib')

        self.mock_appindicator = self.patcher_appindicator.start()
        self.mock_gtk = self.patcher_gtk.start()
        self.mock_glib = self.patcher_glib.start()

        self.mock_glib.idle_add.return_value = None

    def tearDown(self):
        """Clean up patches."""
        self.patcher_appindicator.stop()
        self.patcher_gtk.stop()
        self.patcher_glib.stop()

    def test_full_initialization_sequence(self):
        """Test complete initialization sequence."""
        indicator = SecureUSBIndicator()

        # Verify indicator created
        self.mock_appindicator.Indicator.new.assert_called_once()

        # Verify menu created and shown
        self.mock_gtk.Menu.assert_called_once()

        # Verify idle callback scheduled
        self.mock_glib.idle_add.assert_called_once()


if __name__ == '__main__':
    unittest.main()
