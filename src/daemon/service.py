#!/usr/bin/env python3
"""
Main Daemon Service for SecureUSB

Coordinates USB monitoring, authentication, and authorization.
Runs as root and provides D-Bus interface for user-space GUI.
"""

import sys
import os
import signal
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dbus
import dbus.mainloop.glib
from gi.repository import GLib

from src.daemon.usb_monitor import USBMonitor, USBDevice
from src.daemon.authorization import USBAuthorization, AuthorizationMode
from src.daemon.dbus_service import SecureUSBService
from src.auth import TOTPAuthenticator, RecoveryCodeManager, SecureStorage
from src.utils import USBLogger, EventAction, Config, DeviceWhitelist


class SecureUSBDaemon:
    """Main SecureUSB daemon service."""

    def __init__(self):
        """Initialize the SecureUSB daemon."""
        print("=== SecureUSB Daemon Starting ===\n")

        # Check root privileges
        if os.geteuid() != 0:
            print("Error: SecureUSB daemon must run as root")
            sys.exit(1)

        # Initialize components
        self.config = Config()
        self.logger = USBLogger()
        self.whitelist = DeviceWhitelist()
        self.storage = SecureStorage()

        # Load authentication
        self.totp_auth = None
        self.recovery_codes = []
        self._load_authentication()

        # Initialize D-Bus
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.dbus_service = SecureUSBService(
            self.bus,
            authorization_callback=self._handle_authorization_request,
            config_callback=self._handle_config_request
        )

        # Initialize USB monitor
        self.monitor = USBMonitor(callback=self._handle_device_event)

        # GLib main loop
        self.main_loop = GLib.MainLoop()

        # Pending authorization requests (device_id -> device_info)
        self.pending_authorizations = {}

        # Timeout timers (device_id -> timeout_id)
        self.timeout_timers = {}

        print("[Daemon] Initialization complete")

    def _load_authentication(self):
        """Load TOTP authentication from storage."""
        if not self.storage.is_configured():
            print("[Daemon] Warning: TOTP not configured. Run setup wizard first.")
            print("[Daemon] USB protection will be disabled until configuration is complete.")
            return

        auth_data = self.storage.load_auth_data()

        if auth_data:
            self.totp_auth = TOTPAuthenticator(auth_data['totp_secret'])
            self.recovery_codes = auth_data['recovery_codes']
            print(f"[Daemon] TOTP authentication loaded")
            print(f"[Daemon] Recovery codes available: {len(self.recovery_codes)}")
        else:
            print("[Daemon] Error: Could not load authentication data")

    def _handle_device_event(self, device: USBDevice, action: str):
        """
        Handle USB device connection/disconnection events.

        Args:
            device: USBDevice object
            action: 'add' or 'remove'
        """
        if action == 'add':
            self._handle_device_connected(device)
        elif action == 'remove':
            self._handle_device_disconnected(device)

    def _handle_device_connected(self, device: USBDevice):
        """
        Handle new USB device connection.

        Args:
            device: USBDevice object
        """
        print(f"\n[Daemon] Device connected: {device}")

        # Log the event
        self.logger.log_event(
            EventAction.DEVICE_CONNECTED,
            device_path=device.device_path,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            vendor_name=device.vendor_name,
            product_name=device.product_name,
            serial_number=device.serial_number
        )

        # Check if protection is enabled
        if not self.config.is_enabled():
            print("[Daemon] Protection disabled, allowing device")
            USBAuthorization.allow_device(device.device_id)
            return

        # Check if authentication is configured
        if not self.totp_auth:
            print("[Daemon] TOTP not configured, allowing device")
            USBAuthorization.allow_device(device.device_id)
            return

        # Block the device initially
        print(f"[Daemon] Blocking device {device.device_id} pending authorization")
        USBAuthorization.block_device(device.device_id)

        # Add to pending authorizations
        device_info = device.to_dict()
        self.pending_authorizations[device.device_id] = device_info

        # Emit D-Bus signal for GUI
        self.dbus_service.emit_device_connected(device_info)

        # Check if device is whitelisted
        if device.serial_number and self.whitelist.is_whitelisted(device.serial_number):
            print(f"[Daemon] Device is whitelisted: {device.serial_number}")
            # Note: Still requires TOTP, but GUI can skip showing full dialog

        # Set timeout for auto-deny
        timeout_seconds = self.config.get_timeout()
        timeout_id = GLib.timeout_add_seconds(
            timeout_seconds,
            self._handle_authorization_timeout,
            device.device_id
        )
        self.timeout_timers[device.device_id] = timeout_id

        print(f"[Daemon] Awaiting authorization (timeout: {timeout_seconds}s)")

    def _handle_device_disconnected(self, device: USBDevice):
        """
        Handle USB device disconnection.

        Args:
            device: USBDevice object
        """
        print(f"[Daemon] Device disconnected: {device}")

        # Log the event
        self.logger.log_event(
            EventAction.DEVICE_DISCONNECTED,
            device_path=device.device_path,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            vendor_name=device.vendor_name,
            product_name=device.product_name,
            serial_number=device.serial_number
        )

        # Clean up pending authorization
        if device.device_id in self.pending_authorizations:
            del self.pending_authorizations[device.device_id]

        # Cancel timeout timer
        if device.device_id in self.timeout_timers:
            GLib.source_remove(self.timeout_timers[device.device_id])
            del self.timeout_timers[device.device_id]

        # Emit D-Bus signal
        self.dbus_service.emit_device_disconnected(device.device_id)

    def _handle_authorization_request(self, device_info: dict, totp_code: str, mode: str) -> str:
        """
        Handle authorization request from GUI via D-Bus.

        Args:
            device_info: Device information dictionary
            totp_code: TOTP code or recovery code
            mode: Authorization mode ('full', 'power_only', 'deny')

        Returns:
            Result string ('success', 'auth_failed', 'error')
        """
        device_id = device_info['device_id']

        print(f"\n[Daemon] Authorization request for {device_id}")
        print(f"[Daemon] Mode: {mode}")

        # Cancel timeout timer
        if device_id in self.timeout_timers:
            GLib.source_remove(self.timeout_timers[device_id])
            del self.timeout_timers[device_id]

        # Handle deny
        if mode == 'deny':
            print(f"[Daemon] User denied authorization")
            self._deny_device(device_id, device_info)
            return 'success'

        # Verify authentication
        if not self._verify_authentication(totp_code):
            print(f"[Daemon] Authentication failed")
            self.logger.log_event(
                EventAction.AUTH_FAILED,
                device_path=device_info.get('device_path'),
                vendor_id=device_info.get('vendor_id'),
                product_id=device_info.get('product_id'),
                serial_number=device_info.get('serial_number'),
                success=False,
                details=f"Invalid TOTP code or recovery code"
            )
            return 'auth_failed'

        print(f"[Daemon] Authentication successful")

        # Log successful authentication
        self.logger.log_event(
            EventAction.AUTH_SUCCESS,
            serial_number=device_info.get('serial_number'),
            auth_method='totp',
            success=True
        )

        # Authorize device based on mode
        if mode == 'full':
            return self._authorize_device_full(device_id, device_info)
        elif mode == 'power_only':
            return self._authorize_device_power_only(device_id, device_info)
        else:
            return 'error'

    def _verify_authentication(self, code: str) -> bool:
        """
        Verify TOTP or recovery code.

        Args:
            code: TOTP code or recovery code

        Returns:
            True if valid, False otherwise
        """
        if not code:
            return False

        # Try TOTP first
        if self.totp_auth and self.totp_auth.verify_code(code):
            return True

        # Try recovery codes
        for recovery_hash in self.recovery_codes:
            if RecoveryCodeManager.verify_code(code, recovery_hash):
                # Remove used recovery code
                self.storage.remove_recovery_code(recovery_hash)
                self.recovery_codes.remove(recovery_hash)
                print(f"[Daemon] Recovery code used. Remaining: {len(self.recovery_codes)}")
                return True

        return False

    def _authorize_device_full(self, device_id: str, device_info: dict) -> str:
        """Authorize device with full access."""
        print(f"[Daemon] Authorizing device {device_id} with full access")

        if USBAuthorization.allow_device(device_id):
            self.logger.log_event(
                EventAction.DEVICE_AUTHORIZED,
                device_path=device_info.get('device_path'),
                vendor_id=device_info.get('vendor_id'),
                product_id=device_info.get('product_id'),
                vendor_name=device_info.get('vendor_name'),
                product_name=device_info.get('product_name'),
                serial_number=device_info.get('serial_number'),
                auth_method='totp',
                success=True
            )

            # Update whitelist usage if applicable
            serial = device_info.get('serial_number')
            if serial and self.whitelist.is_whitelisted(serial):
                self.whitelist.update_usage(serial)

            # Emit signal
            self.dbus_service.emit_authorization_result(device_id, 'authorized', True)

            # Clean up
            if device_id in self.pending_authorizations:
                del self.pending_authorizations[device_id]

            return 'success'
        else:
            return 'error'

    def _authorize_device_power_only(self, device_id: str, device_info: dict) -> str:
        """Authorize device with power-only mode."""
        print(f"[Daemon] Authorizing device {device_id} with power-only mode")

        if USBAuthorization.set_power_only_mode(device_id):
            self.logger.log_event(
                EventAction.DEVICE_AUTHORIZED_POWER_ONLY,
                device_path=device_info.get('device_path'),
                vendor_id=device_info.get('vendor_id'),
                product_id=device_info.get('product_id'),
                vendor_name=device_info.get('vendor_name'),
                product_name=device_info.get('product_name'),
                serial_number=device_info.get('serial_number'),
                auth_method='totp',
                success=True,
                details='Power-only mode (charging only)'
            )

            # Emit signal
            self.dbus_service.emit_authorization_result(device_id, 'power_only', True)

            # Clean up
            if device_id in self.pending_authorizations:
                del self.pending_authorizations[device_id]

            return 'success'
        else:
            return 'error'

    def _deny_device(self, device_id: str, device_info: dict):
        """Deny device authorization."""
        print(f"[Daemon] Denying device {device_id}")

        USBAuthorization.block_device(device_id)

        self.logger.log_event(
            EventAction.DEVICE_DENIED,
            device_path=device_info.get('device_path'),
            vendor_id=device_info.get('vendor_id'),
            product_id=device_info.get('product_id'),
            vendor_name=device_info.get('vendor_name'),
            product_name=device_info.get('product_name'),
            serial_number=device_info.get('serial_number'),
            success=True,
            details='User denied authorization'
        )

        # Emit signal
        self.dbus_service.emit_authorization_result(device_id, 'denied', False)

        # Clean up
        if device_id in self.pending_authorizations:
            del self.pending_authorizations[device_id]

    def _handle_authorization_timeout(self, device_id: str) -> bool:
        """
        Handle authorization timeout (auto-deny).

        Args:
            device_id: Device ID

        Returns:
            False to stop the timer
        """
        print(f"\n[Daemon] Authorization timeout for {device_id}")

        if device_id in self.pending_authorizations:
            device_info = self.pending_authorizations[device_id]
            self._deny_device(device_id, device_info)

            self.logger.log_event(
                EventAction.DEVICE_DENIED,
                device_path=device_info.get('device_path'),
                serial_number=device_info.get('serial_number'),
                details='Authorization timeout (auto-deny)'
            )

        # Clean up timer reference
        if device_id in self.timeout_timers:
            del self.timeout_timers[device_id]

        return False  # Don't repeat timer

    def _handle_config_request(self, action: str, value) -> bool:
        """
        Handle configuration change request from D-Bus.

        Args:
            action: Configuration action
            value: Action parameter

        Returns:
            True if successful, False otherwise
        """
        print(f"[Daemon] Config request: {action} = {value}")

        if action == 'set_enabled':
            result = self.config.set_enabled(bool(value))
            if result:
                self.dbus_service.emit_protection_state_changed(bool(value))

                # Set kernel default authorization
                if bool(value):
                    USBAuthorization.set_default_authorization("0")  # Block by default
                else:
                    USBAuthorization.set_default_authorization("1")  # Allow by default

            return result

        elif action == 'add_whitelist':
            # This would need device info - simplified for now
            return True

        elif action == 'remove_whitelist':
            return self.whitelist.remove_device(str(value))

        return False

    def start(self):
        """Start the daemon."""
        print("\n[Daemon] Starting services...")

        # Set USB authorization default to block
        if self.config.is_enabled() and self.totp_auth:
            print("[Daemon] Setting USB authorization default to BLOCK")
            USBAuthorization.set_default_authorization("0")
        else:
            print("[Daemon] USB protection disabled or not configured")

        # Start USB monitor
        self.monitor.start(threaded=True)

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        print("\n[Daemon] SecureUSB daemon is running")
        print("[Daemon] Monitoring USB devices...")
        print("[Daemon] Press Ctrl+C to stop\n")

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            pass

        self.stop()

    def stop(self):
        """Stop the daemon."""
        print("\n[Daemon] Stopping services...")

        # Stop USB monitor
        self.monitor.stop()

        # Cancel all pending timers
        for timeout_id in self.timeout_timers.values():
            GLib.source_remove(timeout_id)

        # Reset USB authorization to allow
        USBAuthorization.set_default_authorization("1")

        print("[Daemon] SecureUSB daemon stopped")

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        print(f"\n[Daemon] Received signal {signum}")
        self.main_loop.quit()


def main():
    """Main entry point."""
    daemon = SecureUSBDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
