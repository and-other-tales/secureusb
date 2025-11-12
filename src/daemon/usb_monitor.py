#!/usr/bin/env python3
"""
USB Monitor Module for SecureUSB

Monitors USB device connection events using pyudev.
Detects when new USB devices are plugged in and triggers authorization workflow.
"""

import pyudev
import threading
import time
from typing import Callable, Optional, Dict
from pathlib import Path


class USBDevice:
    """Represents a USB device with relevant information."""

    def __init__(self, device: pyudev.Device):
        """
        Initialize USBDevice from pyudev.Device.

        Args:
            device: pyudev.Device object
        """
        self.device = device
        self.device_path = device.sys_path
        self.device_id = Path(device.sys_path).name

        # Extract USB device properties
        self.vendor_id = device.get('ID_VENDOR_ID', '')
        self.product_id = device.get('ID_MODEL_ID', '')
        self.vendor_name = device.get('ID_VENDOR', '')
        self.product_name = device.get('ID_MODEL', '')
        self.serial_number = device.get('ID_SERIAL_SHORT', '')
        self.usb_interfaces = device.get('ID_USB_INTERFACES', '')

        # Try to get additional info from sysfs
        self._read_sysfs_attributes()

    def _read_sysfs_attributes(self):
        """Read additional attributes from sysfs if available."""
        device_path = Path(self.device_path)

        try:
            # Read manufacturer
            manufacturer_file = device_path / 'manufacturer'
            if manufacturer_file.exists() and not self.vendor_name:
                self.vendor_name = manufacturer_file.read_text().strip()

            # Read product
            product_file = device_path / 'product'
            if product_file.exists() and not self.product_name:
                self.product_name = product_file.read_text().strip()

            # Read serial
            serial_file = device_path / 'serial'
            if serial_file.exists() and not self.serial_number:
                self.serial_number = serial_file.read_text().strip()

            # Read IDs
            if not self.vendor_id:
                vendor_file = device_path / 'idVendor'
                if vendor_file.exists():
                    self.vendor_id = vendor_file.read_text().strip()

            if not self.product_id:
                product_file = device_path / 'idProduct'
                if product_file.exists():
                    self.product_id = product_file.read_text().strip()

        except Exception as e:
            pass  # Silently ignore errors reading sysfs

    def is_valid_device(self) -> bool:
        """
        Check if this is a valid USB device (not a hub or controller).

        Returns:
            True if valid device, False otherwise
        """
        # Skip USB hubs and root hubs
        if self.device.device_type == 'usb_interface':
            return False

        # Skip devices without vendor/product IDs
        if not self.vendor_id or not self.product_id:
            return False

        # Skip virtual/internal devices (optional)
        # You might want to customize this based on your needs
        return True

    def get_display_name(self) -> str:
        """
        Get human-readable device name.

        Returns:
            Formatted device name
        """
        if self.vendor_name and self.product_name:
            return f"{self.vendor_name} {self.product_name}"
        elif self.product_name:
            return self.product_name
        else:
            return f"USB Device {self.vendor_id}:{self.product_id}"

    def to_dict(self) -> Dict:
        """
        Convert device info to dictionary.

        Returns:
            Dictionary with device information
        """
        return {
            'device_id': self.device_id,
            'device_path': self.device_path,
            'vendor_id': self.vendor_id,
            'product_id': self.product_id,
            'vendor_name': self.vendor_name,
            'product_name': self.product_name,
            'serial_number': self.serial_number,
            'display_name': self.get_display_name()
        }

    def __str__(self) -> str:
        """String representation of device."""
        return f"{self.get_display_name()} ({self.vendor_id}:{self.product_id}) [{self.device_id}]"


class USBMonitor:
    """Monitors USB device connection events."""

    def __init__(self, callback: Optional[Callable[[USBDevice, str], None]] = None):
        """
        Initialize USB monitor.

        Args:
            callback: Function to call when device event occurs.
                     Signature: callback(device: USBDevice, action: str)
                     Actions: 'add', 'remove', 'bind', 'unbind'
        """
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='usb', device_type='usb_device')

        self.callback = callback
        self.observer = None
        self.running = False

        # Track seen devices to avoid duplicates
        self.seen_devices = set()

    def start(self, threaded: bool = True):
        """
        Start monitoring USB events.

        Args:
            threaded: If True, run monitor in background thread
        """
        if self.running:
            print("USB monitor already running")
            return

        self.running = True

        if threaded:
            self.observer = pyudev.MonitorObserver(self.monitor, callback=self._on_event)
            self.observer.start()
            print("USB monitor started (background thread)")
        else:
            # Synchronous monitoring
            print("USB monitor started (blocking)")
            for device in iter(self.monitor.poll, None):
                if not self.running:
                    break
                self._on_event(device)

    def stop(self):
        """Stop monitoring USB events."""
        if not self.running:
            return

        self.running = False

        if self.observer:
            self.observer.stop()
            self.observer = None

        print("USB monitor stopped")

    def _on_event(self, device: pyudev.Device):
        """
        Handle USB device event.

        Args:
            device: pyudev.Device object
        """
        action = device.action

        # Only process add and remove events
        if action not in ['add', 'remove']:
            return

        try:
            usb_device = USBDevice(device)

            # Filter out invalid devices
            if not usb_device.is_valid_device():
                return

            # Track device to avoid duplicates
            device_key = f"{usb_device.device_id}_{action}"

            if action == 'add':
                # Avoid processing the same device multiple times
                if device_key in self.seen_devices:
                    return
                self.seen_devices.add(device_key)

                print(f"[USB Monitor] Device connected: {usb_device}")

                if self.callback:
                    self.callback(usb_device, action)

            elif action == 'remove':
                # Clean up seen devices tracking
                add_key = f"{usb_device.device_id}_add"
                if add_key in self.seen_devices:
                    self.seen_devices.remove(add_key)

                print(f"[USB Monitor] Device disconnected: {usb_device}")

                if self.callback:
                    self.callback(usb_device, action)

        except Exception as e:
            print(f"[USB Monitor] Error processing device event: {e}")

    def scan_existing_devices(self) -> list:
        """
        Scan for currently connected USB devices.

        Returns:
            List of USBDevice objects
        """
        devices = []

        for device in self.context.list_devices(subsystem='usb', DEVTYPE='usb_device'):
            try:
                usb_device = USBDevice(device)

                if usb_device.is_valid_device():
                    devices.append(usb_device)

            except Exception as e:
                print(f"[USB Monitor] Error scanning device: {e}")

        return devices

    def is_running(self) -> bool:
        """
        Check if monitor is running.

        Returns:
            True if running, False otherwise
        """
        return self.running


# Example usage and testing
if __name__ == "__main__":
    import signal
    import sys

    print("=== SecureUSB Monitor Test ===\n")

    def device_event_handler(device: USBDevice, action: str):
        """Handle USB device events."""
        print(f"\n[Event Handler] Action: {action}")
        print(f"  Device: {device.get_display_name()}")
        print(f"  Vendor ID: {device.vendor_id}")
        print(f"  Product ID: {device.product_id}")
        print(f"  Serial: {device.serial_number or 'N/A'}")
        print(f"  Device ID: {device.device_id}")
        print(f"  Path: {device.device_path}")

    # Create monitor with callback
    monitor = USBMonitor(callback=device_event_handler)

    # Scan existing devices
    print("Currently connected USB devices:")
    existing_devices = monitor.scan_existing_devices()

    if existing_devices:
        for i, device in enumerate(existing_devices, 1):
            print(f"  {i}. {device}")
    else:
        print("  No USB devices found")

    print("\nStarting USB monitor...")
    print("Plug in or remove USB devices to see events.")
    print("Press Ctrl+C to stop.\n")

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\nStopping USB monitor...")
        monitor.stop()
        sys.exit(0)

    signal.register(signal.SIGINT, signal_handler)

    # Start monitoring
    monitor.start(threaded=False)
