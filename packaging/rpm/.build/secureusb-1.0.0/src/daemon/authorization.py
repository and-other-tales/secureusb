#!/usr/bin/env python3
"""
USB Authorization Module for SecureUSB

Handles low-level USB device authorization through Linux kernel's sysfs interface.
Requires root privileges to write to /sys/bus/usb/devices/*/authorized
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum


class AuthorizationMode(Enum):
    """USB authorization modes."""
    FULL_ACCESS = "1"  # Full data and power access
    BLOCKED = "0"      # No access (power may still flow on some systems)
    POWER_ONLY = "0"   # Block data, allow charging (same as BLOCKED at kernel level)


class USBAuthorization:
    """Manages USB device authorization at kernel level."""

    USB_DEVICES_PATH = Path("/sys/bus/usb/devices")

    @staticmethod
    def is_root() -> bool:
        """
        Check if running with root privileges.

        Returns:
            True if running as root, False otherwise
        """
        return os.geteuid() == 0

    @staticmethod
    def get_device_path(device_id: str) -> Path:
        """
        Get full sysfs path for a USB device.

        Args:
            device_id: Device ID (e.g., "1-4" from /sys/bus/usb/devices/1-4)

        Returns:
            Path to device in sysfs

        Raises:
            ValueError: If device_id contains invalid characters
        """
        # Validate device_id to prevent path traversal
        import re
        if not re.match(r'^[\w\-.:]+$', device_id):
            raise ValueError(f"Invalid device ID: {device_id}")

        return USBAuthorization.USB_DEVICES_PATH / device_id

    @staticmethod
    def device_exists(device_id: str) -> bool:
        """
        Check if USB device exists in sysfs.

        Args:
            device_id: Device ID

        Returns:
            True if device exists, False otherwise
        """
        device_path = USBAuthorization.get_device_path(device_id)
        return device_path.exists()

    @staticmethod
    def authorize_device(device_id: str, mode: AuthorizationMode = AuthorizationMode.FULL_ACCESS) -> bool:
        """
        Authorize or block a USB device.

        Args:
            device_id: Device ID
            mode: Authorization mode (FULL_ACCESS, BLOCKED, or POWER_ONLY)

        Returns:
            True if successful, False otherwise
        """
        if not USBAuthorization.is_root():
            print("Error: Root privileges required for device authorization")
            return False

        authorized_file = USBAuthorization.get_device_path(device_id) / "authorized"

        if not authorized_file.exists():
            print(f"Error: Device {device_id} not found or authorization not supported")
            return False

        try:
            with open(authorized_file, 'w') as f:
                f.write(mode.value)
            return True

        except PermissionError:
            print(f"Error: Permission denied writing to {authorized_file}")
            return False

        except Exception as e:
            print(f"Error authorizing device {device_id}: {e}")
            return False

    @staticmethod
    def get_authorization_status(device_id: str) -> Optional[bool]:
        """
        Get current authorization status of a device.

        Args:
            device_id: Device ID

        Returns:
            True if authorized, False if blocked, None if error
        """
        authorized_file = USBAuthorization.get_device_path(device_id) / "authorized"

        if not authorized_file.exists():
            return None

        try:
            with open(authorized_file, 'r') as f:
                value = f.read().strip()
                return value == "1"

        except Exception as e:
            print(f"Error reading authorization status for {device_id}: {e}")
            return None

    @staticmethod
    def block_device(device_id: str) -> bool:
        """
        Block a USB device.

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        return USBAuthorization.authorize_device(device_id, AuthorizationMode.BLOCKED)

    @staticmethod
    def allow_device(device_id: str) -> bool:
        """
        Allow full access to a USB device.

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        return USBAuthorization.authorize_device(device_id, AuthorizationMode.FULL_ACCESS)

    @staticmethod
    def set_power_only_mode(device_id: str) -> bool:
        """
        Set device to power-only mode (charging only, no data).

        Note: At kernel level, this is the same as blocking. The device
        will receive power but data communication is blocked.

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        # Block the device first
        if not USBAuthorization.block_device(device_id):
            return False

        # Optionally unbind USB interfaces to ensure no data transfer
        # This is more aggressive and ensures no driver interaction
        return USBAuthorization._unbind_interfaces(device_id)

    @staticmethod
    def _unbind_interfaces(device_id: str) -> bool:
        """
        Unbind all USB interfaces for a device.

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        device_path = USBAuthorization.get_device_path(device_id)

        try:
            # Find all interface subdirectories (e.g., 1-4:1.0)
            for item in device_path.iterdir():
                if ':' in item.name:  # USB interface naming convention
                    driver_path = item / "driver"
                    if driver_path.exists() and driver_path.is_symlink():
                        # Unbind the interface
                        unbind_path = driver_path / "unbind"
                        if unbind_path.exists():
                            try:
                                with open(unbind_path, 'w') as f:
                                    f.write(item.name)
                            except Exception as e:
                                # Some interfaces may not support unbinding
                                print(f"Warning: Could not unbind interface {item.name}: {e}")

            return True

        except Exception as e:
            print(f"Error unbinding interfaces for {device_id}: {e}")
            return False

    @staticmethod
    def set_default_authorization(mode: str = "0") -> bool:
        """
        Set default authorization mode for new USB devices.

        Args:
            mode: "0" to block by default, "1" to allow by default, "2" for internal only

        Returns:
            True if successful, False otherwise
        """
        if not USBAuthorization.is_root():
            print("Error: Root privileges required")
            return False

        # Find all USB controllers
        try:
            for controller_path in USBAuthorization.USB_DEVICES_PATH.glob("usb*"):
                authorized_default = controller_path / "authorized_default"

                if authorized_default.exists():
                    try:
                        with open(authorized_default, 'w') as f:
                            f.write(mode)
                    except Exception as e:
                        print(f"Error setting authorized_default for {controller_path.name}: {e}")

            return True

        except Exception as e:
            print(f"Error setting default authorization: {e}")
            return False

    @staticmethod
    def read_device_attribute(device_id: str, attribute: str) -> Optional[str]:
        """
        Read a device attribute from sysfs.

        Args:
            device_id: Device ID
            attribute: Attribute name (e.g., 'idVendor', 'product', 'serial')

        Returns:
            Attribute value or None if not found
        """
        attr_file = USBAuthorization.get_device_path(device_id) / attribute

        if not attr_file.exists():
            return None

        try:
            with open(attr_file, 'r') as f:
                return f.read().strip()
        except Exception as e:
            # Log error for debugging but don't expose to user
            import sys
            print(f"[DEBUG] Error reading device attribute {attribute}: {e}", file=sys.stderr)
            return None

    @staticmethod
    def get_device_info(device_id: str) -> Optional[dict]:
        """
        Get detailed information about a USB device.

        Args:
            device_id: Device ID

        Returns:
            Dictionary with device information or None if device not found
        """
        if not USBAuthorization.device_exists(device_id):
            return None

        info = {
            'device_id': device_id,
            'vendor_id': USBAuthorization.read_device_attribute(device_id, 'idVendor'),
            'product_id': USBAuthorization.read_device_attribute(device_id, 'idProduct'),
            'vendor_name': USBAuthorization.read_device_attribute(device_id, 'manufacturer'),
            'product_name': USBAuthorization.read_device_attribute(device_id, 'product'),
            'serial_number': USBAuthorization.read_device_attribute(device_id, 'serial'),
            'speed': USBAuthorization.read_device_attribute(device_id, 'speed'),
            'authorized': USBAuthorization.get_authorization_status(device_id)
        }

        return info


# Example usage and testing
if __name__ == "__main__":
    import sys

    print("=== SecureUSB Authorization Module Test ===\n")

    if not USBAuthorization.is_root():
        print("Warning: Not running as root. Authorization functions will fail.")
        print("Run with: sudo python3 authorization.py\n")

    # List available USB devices
    print("Available USB devices:")
    if USBAuthorization.USB_DEVICES_PATH.exists():
        for device_path in sorted(USBAuthorization.USB_DEVICES_PATH.iterdir()):
            device_id = device_path.name

            # Skip USB controllers (usb1, usb2, etc.)
            if device_id.startswith('usb'):
                continue

            # Skip if it doesn't look like a device ID (should contain '-' or ':')
            if '-' not in device_id and ':' not in device_id:
                continue

            info = USBAuthorization.get_device_info(device_id)

            if info and info['product_name']:
                status = "✓ Authorized" if info['authorized'] else "✗ Blocked"
                print(f"\n  Device: {device_id}")
                print(f"  Name: {info['vendor_name']} {info['product_name']}")
                print(f"  IDs: {info['vendor_id']}:{info['product_id']}")
                print(f"  Serial: {info['serial_number'] or 'N/A'}")
                print(f"  Status: {status}")
    else:
        print("  USB devices path not found!")

    print(f"\nRunning as root: {USBAuthorization.is_root()}")
