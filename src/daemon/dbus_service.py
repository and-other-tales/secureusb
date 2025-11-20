#!/usr/bin/env python3
"""
D-Bus Service for SecureUSB

Provides D-Bus interface for communication between the root daemon
and user-space GUI applications.
"""

import dbus
import dbus.service
import dbus.mainloop.glib
import subprocess
from gi.repository import GLib
from typing import Dict, List, Optional, Callable


# D-Bus service configuration
DBUS_SERVICE_NAME = "org.secureusb.Daemon"
DBUS_OBJECT_PATH = "/org/secureusb/Daemon"
DBUS_INTERFACE_NAME = "org.secureusb.Daemon"


class SecureUSBService(dbus.service.Object):
    """D-Bus service for SecureUSB daemon."""

    def __init__(self, bus: dbus.SystemBus, authorization_callback: Callable, config_callback: Callable):
        """
        Initialize D-Bus service.

        Args:
            bus: D-Bus system bus connection
            authorization_callback: Function to call for authorization requests
            config_callback: Function to call for configuration changes
        """
        bus_name = dbus.service.BusName(DBUS_SERVICE_NAME, bus=bus)
        super().__init__(bus_name, DBUS_OBJECT_PATH)

        self.authorization_callback = authorization_callback
        self.config_callback = config_callback

        # Pending authorization requests
        self.pending_requests = {}

        print(f"[D-Bus] Service registered: {DBUS_SERVICE_NAME}")

    def _check_polkit_authorization(self, sender: str, action_id: str) -> bool:
        """
        Verify Polkit authorization for sensitive operations.

        Args:
            sender: D-Bus sender (bus name)
            action_id: Polkit action ID

        Returns:
            True if authorized, False otherwise
        """
        try:
            # Get the process ID of the sender
            bus = dbus.SystemBus()
            dbus_obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
            dbus_iface = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')
            pid = dbus_iface.GetConnectionUnixProcessID(sender)

            # Use pkcheck to verify authorization
            result = subprocess.run(
                ['pkcheck', '--action-id', action_id, '--process', str(pid)],
                capture_output=True,
                text=True
            )

            return result.returncode == 0
        except Exception as e:
            print(f"[D-Bus] Polkit check failed: {e}")
            return False

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='b')
    def Ping(self):
        """
        Ping service to check if daemon is running.

        Returns:
            True if daemon is running
        """
        return True

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='s')
    def GetVersion(self):
        """
        Get SecureUSB version.

        Returns:
            Version string
        """
        return "1.0.0"

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='b')
    def IsEnabled(self):
        """
        Check if USB protection is enabled.

        Returns:
            True if enabled, False otherwise
        """
        try:
            from ..utils import Config
            config = Config()
            return config.is_enabled()
        except:
            return True

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='b', out_signature='b', sender_keyword='sender')
    def SetEnabled(self, enabled, sender=None):
        """
        Enable or disable USB protection.

        Args:
            enabled: True to enable, False to disable
            sender: D-Bus sender (automatically provided)

        Returns:
            True if successful, False otherwise
        """
        # Security: Verify Polkit authorization before allowing enable/disable
        if not self._check_polkit_authorization(sender, 'org.secureusb.enable-disable'):
            print(f"[D-Bus] SetEnabled denied for sender {sender}: insufficient privileges")
            return False

        if self.config_callback:
            return self.config_callback('set_enabled', enabled)
        return False

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='ssssssss', out_signature='s')
    def AuthorizeDevice(self, device_id, vendor_id, product_id, vendor_name,
                        product_name, serial_number, totp_code, auth_mode):
        """
        Authorize a USB device with TOTP authentication.

        Args:
            device_id: Device ID (e.g., "1-4")
            vendor_id: USB vendor ID
            product_id: USB product ID
            vendor_name: Vendor name
            product_name: Product name
            serial_number: Device serial number
            totp_code: TOTP authentication code
            auth_mode: Authorization mode ("full", "power_only", "deny")

        Returns:
            Result: "success", "auth_failed", "error", or error message
        """
        device_info = {
            'device_id': str(device_id),
            'vendor_id': str(vendor_id),
            'product_id': str(product_id),
            'vendor_name': str(vendor_name),
            'product_name': str(product_name),
            'serial_number': str(serial_number)
        }

        if self.authorization_callback:
            result = self.authorization_callback(
                device_info,
                str(totp_code),
                str(auth_mode)
            )
            return str(result)

        return "error"

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='s', out_signature='b')
    def DenyDevice(self, device_id):
        """
        Deny authorization for a USB device.

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        if self.authorization_callback:
            result = self.authorization_callback(
                {'device_id': str(device_id)},
                '',
                'deny'
            )
            return result == "success"

        return False

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='aa{ss}')
    def GetPendingDevices(self):
        """
        Get list of devices awaiting authorization.

        Returns:
            List of device info dictionaries
        """
        return [
            dbus.Dictionary(device, signature='ss')
            for device in self.pending_requests.values()
        ]

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='aa{sv}')
    def GetRecentEvents(self):
        """
        Get recent USB authorization events.

        Returns:
            List of event dictionaries
        """
        try:
            from ..utils import USBLogger

            logger = USBLogger()
            events = logger.get_recent_events(limit=50)

            # Convert to D-Bus compatible format
            dbus_events = []
            for event in events:
                dbus_event = {}
                for key, value in event.items():
                    if value is None:
                        dbus_event[key] = dbus.String('')
                    elif isinstance(value, (int, float)):
                        dbus_event[key] = dbus.Double(value)
                    else:
                        dbus_event[key] = dbus.String(str(value))

                dbus_events.append(dbus.Dictionary(dbus_event, signature='sv'))

            return dbus.Array(dbus_events, signature='a{sv}')

        except Exception as e:
            print(f"[D-Bus] Error getting recent events: {e}")
            return dbus.Array([], signature='a{sv}')

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='', out_signature='a{ss}')
    def GetStatistics(self):
        """
        Get usage statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            from ..utils import USBLogger

            logger = USBLogger()
            stats = logger.get_statistics()

            # Convert to D-Bus compatible format
            dbus_stats = {}
            for key, value in stats.items():
                if isinstance(value, dict):
                    dbus_stats[key] = str(value)
                else:
                    dbus_stats[key] = str(value)

            return dbus.Dictionary(dbus_stats, signature='ss')

        except Exception as e:
            print(f"[D-Bus] Error getting statistics: {e}")
            return dbus.Dictionary({}, signature='ss')

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='a{ss}', out_signature='b')
    def AddToWhitelist(self, device_info):
        """
        Add device to whitelist.

        Args:
            device_info: Dictionary with device metadata

        Returns:
            True if successful, False otherwise
        """
        if self.config_callback and isinstance(device_info, dict):
            normalized = {
                str(key): str(value)
                for key, value in device_info.items()
                if value is not None
            }
            return self.config_callback('add_whitelist', normalized)
        return False

    @dbus.service.method(DBUS_INTERFACE_NAME, in_signature='s', out_signature='b')
    def RemoveFromWhitelist(self, serial_number):
        """
        Remove device from whitelist.

        Args:
            serial_number: Device serial number

        Returns:
            True if successful, False otherwise
        """
        if self.config_callback:
            return self.config_callback('remove_whitelist', str(serial_number))
        return False

    @dbus.service.signal(DBUS_INTERFACE_NAME, signature='a{ss}')
    def DeviceConnected(self, device_info):
        """
        Signal emitted when a new USB device is connected.

        Args:
            device_info: Dictionary with device information
        """
        pass  # Signal body is automatically generated

    @dbus.service.signal(DBUS_INTERFACE_NAME, signature='s')
    def DeviceDisconnected(self, device_id):
        """
        Signal emitted when a USB device is disconnected.

        Args:
            device_id: Device ID
        """
        pass

    @dbus.service.signal(DBUS_INTERFACE_NAME, signature='ssb')
    def AuthorizationResult(self, device_id, result, success):
        """
        Signal emitted when device authorization is complete.

        Args:
            device_id: Device ID
            result: Result message
            success: True if authorized, False if denied
        """
        pass

    @dbus.service.signal(DBUS_INTERFACE_NAME, signature='b')
    def ProtectionStateChanged(self, enabled):
        """
        Signal emitted when USB protection is enabled/disabled.

        Args:
            enabled: True if enabled, False if disabled
        """
        pass

    def emit_device_connected(self, device_info: Dict):
        """
        Emit DeviceConnected signal.

        Args:
            device_info: Device information dictionary
        """
        # Store in pending requests
        device_id = device_info.get('device_id', '')
        self.pending_requests[device_id] = device_info

        # Convert to D-Bus types
        dbus_info = {}
        for key, value in device_info.items():
            dbus_info[key] = str(value) if value else ''

        self.DeviceConnected(dbus.Dictionary(dbus_info, signature='ss'))

    def emit_device_disconnected(self, device_id: str):
        """
        Emit DeviceDisconnected signal.

        Args:
            device_id: Device ID
        """
        # Remove from pending requests
        if device_id in self.pending_requests:
            del self.pending_requests[device_id]

        self.DeviceDisconnected(device_id)

    def emit_authorization_result(self, device_id: str, result: str, success: bool):
        """
        Emit AuthorizationResult signal.

        Args:
            device_id: Device ID
            result: Result message
            success: True if authorized, False if denied
        """
        # Remove from pending requests
        if device_id in self.pending_requests:
            del self.pending_requests[device_id]

        self.AuthorizationResult(device_id, result, success)

    def emit_protection_state_changed(self, enabled: bool):
        """
        Emit ProtectionStateChanged signal.

        Args:
            enabled: True if enabled, False if disabled
        """
        self.ProtectionStateChanged(enabled)


class DBusClient:
    """Client for communicating with SecureUSB D-Bus service."""

    def __init__(self, bus_type: str = 'system'):
        """
        Initialize D-Bus client.

        Args:
            bus_type: 'system' or 'session' bus
        """
        if bus_type == 'system':
            self.bus = dbus.SystemBus()
        else:
            self.bus = dbus.SessionBus()

        try:
            self.proxy = self.bus.get_object(DBUS_SERVICE_NAME, DBUS_OBJECT_PATH)
            self.interface = dbus.Interface(self.proxy, DBUS_INTERFACE_NAME)
        except dbus.DBusException as e:
            print(f"[D-Bus Client] Error connecting to service: {e}")
            self.proxy = None
            self.interface = None

    def is_connected(self) -> bool:
        """Check if connected to daemon."""
        if not self.interface:
            return False

        try:
            return bool(self.interface.Ping())
        except:
            return False

    def authorize_device(self, device_info: Dict, totp_code: str, mode: str = 'full') -> str:
        """Authorize a USB device."""
        if not self.interface:
            return "error: not connected"

        try:
            return str(self.interface.AuthorizeDevice(
                device_info.get('device_id', ''),
                device_info.get('vendor_id', ''),
                device_info.get('product_id', ''),
                device_info.get('vendor_name', ''),
                device_info.get('product_name', ''),
                device_info.get('serial_number', ''),
                totp_code,
                mode
            ))
        except Exception as e:
            return f"error: {e}"

    def deny_device(self, device_id: str) -> bool:
        """Deny authorization for a device."""
        if not self.interface:
            return False

        try:
            return bool(self.interface.DenyDevice(device_id))
        except:
            return False

    def add_to_whitelist(self, device_info: Dict[str, str]) -> bool:
        """Add a device to the whitelist via D-Bus."""
        if not self.interface or not device_info:
            return False

        try:
            payload = {
                str(key): str(value)
                for key, value in device_info.items()
                if value is not None
            }
            return bool(self.interface.AddToWhitelist(dbus.Dictionary(payload, signature='ss')))
        except Exception as e:
            print(f"[D-Bus Client] Error adding to whitelist: {e}")
            return False

    def connect_to_signal(self, signal_name: str, handler: Callable):
        """Connect to a D-Bus signal."""
        if not self.proxy:
            return

        try:
            self.proxy.connect_to_signal(signal_name, handler, dbus_interface=DBUS_INTERFACE_NAME)
        except Exception as e:
            print(f"[D-Bus Client] Error connecting to signal {signal_name}: {e}")


# Example usage
if __name__ == "__main__":
    print("=== SecureUSB D-Bus Service Test ===\n")

    # Initialize D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # Test client connection
    print("Testing D-Bus client connection...")
    client = DBusClient('system')

    if client.is_connected():
        print("✓ Connected to SecureUSB daemon")
        version = client.interface.GetVersion()
        print(f"  Daemon version: {version}")
    else:
        print("✗ Could not connect to SecureUSB daemon")
        print("  Make sure the daemon is running with root privileges")

    print("\nNote: To start the service, run the main daemon with root privileges")
