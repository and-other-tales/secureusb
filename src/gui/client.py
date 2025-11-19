#!/usr/bin/env python3
"""
SecureUSB GUI Client

Main GUI application that monitors D-Bus for USB device events
and displays authorization dialogs.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio

import sys
import dbus
import dbus.mainloop.glib
from pathlib import Path
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.daemon.dbus_service import DBusClient, DBUS_INTERFACE_NAME
from src.gui.auth_dialog import AuthorizationDialog


class SecureUSBClient(Adw.Application):
    """Main SecureUSB client application."""

    def __init__(self):
        """Initialize the application."""
        super().__init__(application_id="org.secureusb.Client")

        # Initialize D-Bus
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        self.dbus_client = None
        self.active_dialogs = {}  # device_id -> dialog

    def do_activate(self):
        """Called when application is activated."""
        # Connect to D-Bus daemon
        self.dbus_client = DBusClient('system')

        if not self.dbus_client.is_connected():
            print("Error: Could not connect to SecureUSB daemon")
            print("Make sure the daemon is running with root privileges:")
            print("  sudo systemctl start secureusb")
            self.quit()
            return

        print("SecureUSB Client: Connected to daemon")

        # Connect to D-Bus signals
        self._connect_signals()

        # Check for pending devices
        self._check_pending_devices()

        print("SecureUSB Client: Monitoring for USB devices...")

    def _connect_signals(self):
        """Connect to D-Bus signals from daemon."""
        self.dbus_client.connect_to_signal('DeviceConnected', self._on_device_connected)
        self.dbus_client.connect_to_signal('DeviceDisconnected', self._on_device_disconnected)
        self.dbus_client.connect_to_signal('AuthorizationResult', self._on_authorization_result)

    def _check_pending_devices(self):
        """Check if there are any devices already pending authorization."""
        try:
            pending_devices = self.dbus_client.interface.GetPendingDevices()

            for device_dict in pending_devices:
                # Convert dbus.Dictionary to regular dict
                device_info = {str(k): str(v) for k, v in device_dict.items()}
                self._show_authorization_dialog(device_info)

        except Exception as e:
            print(f"Error checking pending devices: {e}")

    def _on_device_connected(self, device_dict):
        """
        Handle DeviceConnected signal from daemon.

        Args:
            device_dict: D-Bus dictionary with device information
        """
        # Convert dbus.Dictionary to regular dict
        device_info = {str(k): str(v) for k, v in device_dict.items()}

        print(f"Device connected: {device_info.get('display_name', 'Unknown')}")

        self._show_authorization_dialog(device_info)

    def _on_device_disconnected(self, device_id):
        """
        Handle DeviceDisconnected signal from daemon.

        Args:
            device_id: Device ID
        """
        print(f"Device disconnected: {device_id}")

        # Close authorization dialog if open
        if device_id in self.active_dialogs:
            dialog = self.active_dialogs[device_id]
            dialog.close()
            del self.active_dialogs[device_id]

    def _on_authorization_result(self, device_id, result, success):
        """
        Handle AuthorizationResult signal from daemon.

        Args:
            device_id: Device ID
            result: Result message
            success: True if authorized, False if denied
        """
        print(f"Authorization result for {device_id}: {result} (success={success})")

        # Close dialog if open
        if device_id in self.active_dialogs:
            dialog = self.active_dialogs[device_id]
            dialog.close()
            del self.active_dialogs[device_id]

        # Show notification
        self._show_notification(result, success)

    def _show_authorization_dialog(self, device_info: dict):
        """
        Show authorization dialog for a device.

        Args:
            device_info: Device information dictionary
        """
        device_id = device_info.get('device_id', '')

        # Don't show multiple dialogs for same device
        if device_id in self.active_dialogs:
            return

        # Create and show dialog
        dialog = AuthorizationDialog(device_info, self.dbus_client)
        dialog.set_application(self)

        # Track active dialog
        self.active_dialogs[device_id] = dialog

        # Clean up when closed
        dialog.connect('close-request', lambda d: self._on_dialog_closed(device_id))

        dialog.present()

    def _on_dialog_closed(self, device_id: str):
        """
        Handle dialog close event.

        Args:
            device_id: Device ID
        """
        if device_id in self.active_dialogs:
            del self.active_dialogs[device_id]

        return False

    def _show_notification(self, message: str, success: bool):
        """
        Show a notification.

        Args:
            message: Notification message
            success: True for success, False for error
        """
        icon_name = "security-high" if success else "security-low"
        summary = "SecureUSB"

        try:
            notification = Gio.Notification.new(summary)
            notification.set_body(message)
            notification.set_icon(Gio.ThemedIcon.new(icon_name))

            notification_id = f"secureusb-{int(time.time() * 1000)}"
            self.send_notification(notification_id, notification)
        except Exception as e:
            status = "✓" if success else "✗"
            print(f"{status} {message} (notification error: {e})")


def main():
    """Main entry point."""
    app = SecureUSBClient()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
