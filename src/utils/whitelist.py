#!/usr/bin/env python3
"""
Whitelist Module for SecureUSB

Manages trusted USB devices that can be authorized with reduced friction.
Note: Even whitelisted devices still require TOTP authentication.
"""

import json
import os
import stat
import time
from pathlib import Path
from typing import List, Dict, Optional

from .paths import resolve_config_dir


class DeviceWhitelist:
    """Manages whitelist of trusted USB devices."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize whitelist manager.

        Args:
            config_dir: Configuration directory. If None, uses the shared SecureUSB config dir.
        """
        if config_dir is None:
            self.config_dir = resolve_config_dir()
        else:
            self.config_dir = Path(config_dir)

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.whitelist_file = self.config_dir / "whitelist.json"

        self.devices = self._load_whitelist()
        self._normalize_in_memory_devices()

    def _load_whitelist(self) -> Dict[str, Dict]:
        """
        Load whitelist from file.

        Returns:
            Dictionary mapping serial numbers to device info
        """
        if self.whitelist_file.exists():
            try:
                with open(self.whitelist_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading whitelist: {e}")
                return {}
        return {}

    def _save_whitelist(self) -> bool:
        """
        Save whitelist to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.whitelist_file, 'w') as f:
                json.dump(self.devices, f, indent=2)
            # Security: Set restrictive permissions (0600 - owner read/write only)
            os.chmod(self.whitelist_file, stat.S_IRUSR | stat.S_IWUSR)
            return True
        except Exception as e:
            print(f"Error saving whitelist: {e}")
            return False

    def _normalize_in_memory_devices(self):
        """Ensure all in-memory entries contain the expected bookkeeping fields."""
        normalized = {}
        for serial, device_info in self.devices.items():
            try:
                normalized[serial] = self._normalize_device_entry(serial, device_info)
            except Exception:
                # Skip entries we cannot normalize; callers can re-import if needed.
                continue
        self.devices = normalized

    def _normalize_device_entry(self, serial_number: str, data: Optional[Dict]) -> Dict:
        """Return a device dictionary with all required keys and sane defaults."""
        data = data or {}

        vendor_id = str(data.get('vendor_id') or '0000')
        product_id = str(data.get('product_id') or '0000')
        vendor_name = data.get('vendor_name') or f"Vendor {vendor_id}"
        product_name = data.get('product_name') or f"Product {product_id}"
        notes = data.get('notes') or ""

        def _coerce_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _coerce_int(value, default: int = 0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        added_ts = _coerce_float(data.get('added_timestamp')) or time.time()
        last_used_input = data.get('last_used_timestamp')
        last_used_ts = _coerce_float(last_used_input) if last_used_input is not None else None

        return {
            'serial_number': serial_number,
            'vendor_id': vendor_id,
            'product_id': product_id,
            'vendor_name': vendor_name,
            'product_name': product_name,
            'notes': notes,
            'added_timestamp': added_ts,
            'last_used_timestamp': last_used_ts,
            'use_count': _coerce_int(data.get('use_count'), 0)
        }

    def add_device(self,
                   serial_number: str,
                   vendor_id: str,
                   product_id: str,
                   vendor_name: Optional[str] = None,
                   product_name: Optional[str] = None,
                   notes: Optional[str] = None) -> bool:
        """
        Add device to whitelist.

        Args:
            serial_number: Device serial number (unique identifier)
            vendor_id: USB vendor ID
            product_id: USB product ID
            vendor_name: Human-readable vendor name
            product_name: Human-readable product name
            notes: Optional notes about the device

        Returns:
            True if added successfully, False otherwise
        """
        if not serial_number:
            print("Error: Serial number is required for whitelisting")
            return False

        self.devices[serial_number] = {
            'serial_number': serial_number,
            'vendor_id': vendor_id,
            'product_id': product_id,
            'vendor_name': vendor_name or f"Vendor {vendor_id}",
            'product_name': product_name or f"Product {product_id}",
            'notes': notes or "",
            'added_timestamp': time.time(),
            'last_used_timestamp': None,
            'use_count': 0
        }

        return self._save_whitelist()

    def remove_device(self, serial_number: str) -> bool:
        """
        Remove device from whitelist.

        Args:
            serial_number: Device serial number

        Returns:
            True if removed successfully, False otherwise
        """
        if serial_number in self.devices:
            del self.devices[serial_number]
            return self._save_whitelist()
        return False

    def is_whitelisted(self, serial_number: str) -> bool:
        """
        Check if device is whitelisted.

        Args:
            serial_number: Device serial number

        Returns:
            True if whitelisted, False otherwise
        """
        return serial_number in self.devices

    def get_device(self, serial_number: str) -> Optional[Dict]:
        """
        Get device information from whitelist.

        Args:
            serial_number: Device serial number

        Returns:
            Device info dictionary or None if not found
        """
        return self.devices.get(serial_number)

    def update_usage(self, serial_number: str) -> bool:
        """
        Update last used timestamp and increment use count.

        Args:
            serial_number: Device serial number

        Returns:
            True if updated successfully, False otherwise
        """
        if serial_number in self.devices:
            self.devices[serial_number]['last_used_timestamp'] = time.time()
            self.devices[serial_number]['use_count'] += 1
            return self._save_whitelist()
        return False

    def get_all_devices(self) -> List[Dict]:
        """
        Get all whitelisted devices.

        Returns:
            List of device info dictionaries
        """
        return list(self.devices.values())

    def clear_all(self) -> bool:
        """
        Remove all devices from whitelist.

        Returns:
            True if successful, False otherwise
        """
        self.devices = {}
        return self._save_whitelist()

    def get_count(self) -> int:
        """
        Get number of whitelisted devices.

        Returns:
            Number of devices in whitelist
        """
        return len(self.devices)

    def update_device_info(self,
                          serial_number: str,
                          vendor_name: Optional[str] = None,
                          product_name: Optional[str] = None,
                          notes: Optional[str] = None) -> bool:
        """
        Update device information.

        Args:
            serial_number: Device serial number
            vendor_name: New vendor name (if provided)
            product_name: New product name (if provided)
            notes: New notes (if provided)

        Returns:
            True if updated successfully, False otherwise
        """
        if serial_number not in self.devices:
            return False

        device = self.devices[serial_number]

        if vendor_name is not None:
            device['vendor_name'] = vendor_name

        if product_name is not None:
            device['product_name'] = product_name

        if notes is not None:
            device['notes'] = notes

        return self._save_whitelist()

    def export_whitelist(self, export_path: Path) -> bool:
        """
        Export whitelist to file.

        Args:
            export_path: Path to export file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(export_path, 'w') as f:
                json.dump(self.devices, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting whitelist: {e}")
            return False

    def import_whitelist(self, import_path: Path, merge: bool = False) -> bool:
        """
        Import whitelist from file.

        Args:
            import_path: Path to import file
            merge: If True, merge with existing whitelist. If False, replace.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(import_path, 'r') as f:
                imported_devices = json.load(f)

            if not isinstance(imported_devices, dict):
                raise ValueError("Whitelist export must be a mapping of serial numbers to metadata")

            normalized_devices = {}
            for serial, device_info in imported_devices.items():
                serial_str = str(serial).strip()
                if not serial_str:
                    continue
                normalized_devices[serial_str] = self._normalize_device_entry(serial_str, device_info)

            if not merge:
                self.devices = normalized_devices
            else:
                # Merge, updating existing metadata while preserving usage stats
                for serial, device_info in normalized_devices.items():
                    existing = self.devices.get(serial)
                    if not existing:
                        self.devices[serial] = device_info
                        continue

                    merged = existing.copy()
                    merged.update(device_info)

                    for key in ('use_count', 'last_used_timestamp', 'added_timestamp'):
                        merged[key] = existing.get(key)

                    merged['serial_number'] = serial
                    self.devices[serial] = merged

            return self._save_whitelist()

        except Exception as e:
            print(f"Error importing whitelist: {e}")
            return False

    def search_devices(self, query: str) -> List[Dict]:
        """
        Search for devices by name, serial, vendor, or product.

        Args:
            query: Search query string

        Returns:
            List of matching device dictionaries
        """
        query_lower = query.lower()
        results = []

        for device in self.devices.values():
            serial = (device.get('serial_number') or '').lower()
            vendor = (device.get('vendor_name') or '').lower()
            product = (device.get('product_name') or '').lower()
            notes = (device.get('notes') or '').lower()

            if (query_lower in serial or
                query_lower in vendor or
                query_lower in product or
                query_lower in notes):
                results.append(device)

        return results


class DeviceInfo:
    """Helper class for USB device information."""

    @staticmethod
    def parse_device_path(device_path: str) -> Optional[str]:
        """
        Extract device ID from sysfs path.

        Args:
            device_path: Path like /sys/bus/usb/devices/1-4

        Returns:
            Device ID like "1-4" or None if invalid
        """
        try:
            if not device_path:
                return None
            device_id = device_path.split('/')[-1]
            return device_id if device_id else None
        except:
            return None

    @staticmethod
    def read_sysfs_attr(device_path: str, attr: str) -> Optional[str]:
        """
        Read a sysfs attribute for a USB device.

        Args:
            device_path: Path to device in sysfs
            attr: Attribute name (e.g., 'idVendor', 'serial')

        Returns:
            Attribute value or None if not found
        """
        try:
            attr_path = Path(device_path) / attr
            if attr_path.exists():
                return attr_path.read_text().strip()
        except:
            pass
        return None


# Example usage and testing
if __name__ == "__main__":
    from datetime import datetime

    print("=== SecureUSB Whitelist Test ===\n")

    whitelist = DeviceWhitelist()

    # Add test devices
    whitelist.add_device(
        serial_number="ABC123456",
        vendor_id="046d",
        product_id="c52b",
        vendor_name="Logitech",
        product_name="Unifying Receiver",
        notes="My wireless mouse/keyboard receiver"
    )

    whitelist.add_device(
        serial_number="XYZ789012",
        vendor_id="0781",
        product_id="5583",
        vendor_name="SanDisk",
        product_name="Ultra USB 3.0",
        notes="My personal USB drive"
    )

    # Display whitelisted devices
    print("Whitelisted Devices:")
    for device in whitelist.get_all_devices():
        added_time = datetime.fromtimestamp(device['added_timestamp']).strftime('%Y-%m-%d')
        print(f"\n  Serial: {device['serial_number']}")
        print(f"  Device: {device['vendor_name']} {device['product_name']}")
        print(f"  IDs: {device['vendor_id']}:{device['product_id']}")
        print(f"  Added: {added_time}")
        print(f"  Uses: {device['use_count']}")
        if device['notes']:
            print(f"  Notes: {device['notes']}")

    # Test checking
    print(f"\nIs ABC123456 whitelisted? {whitelist.is_whitelisted('ABC123456')}")
    print(f"Is UNKNOWN123 whitelisted? {whitelist.is_whitelisted('UNKNOWN123')}")

    # Test usage update
    whitelist.update_usage('ABC123456')
    device = whitelist.get_device('ABC123456')
    print(f"\nAfter usage update:")
    print(f"  Use count: {device['use_count']}")

    # Test search
    results = whitelist.search_devices('logitech')
    print(f"\nSearch for 'logitech': {len(results)} result(s)")

    print(f"\nTotal whitelisted devices: {whitelist.get_count()}")
    print(f"Whitelist file: {whitelist.whitelist_file}")
