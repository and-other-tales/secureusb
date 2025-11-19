#!/usr/bin/env python3
"""
Unit tests for whitelist module.
"""

import json
import unittest
import tempfile
import shutil
from pathlib import Path
from src.utils.whitelist import DeviceWhitelist, DeviceInfo


class TestDeviceWhitelist(unittest.TestCase):
    """Test cases for DeviceWhitelist class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.whitelist = DeviceWhitelist(config_dir=self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test whitelist initialization."""
        self.assertTrue(self.test_dir.exists())
        self.assertEqual(self.whitelist.get_count(), 0)

    def test_add_device(self):
        """Test adding a device to whitelist."""
        result = self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Logitech",
            product_name="USB Receiver"
        )

        self.assertTrue(result)
        self.assertEqual(self.whitelist.get_count(), 1)

    def test_add_device_without_serial(self):
        """Test adding device without serial number fails."""
        result = self.whitelist.add_device(
            serial_number="",
            vendor_id="046d",
            product_id="c52b"
        )

        self.assertFalse(result)

    def test_is_whitelisted(self):
        """Test checking if device is whitelisted."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b"
        )

        self.assertTrue(self.whitelist.is_whitelisted("ABC123"))
        self.assertFalse(self.whitelist.is_whitelisted("XYZ789"))

    def test_get_device(self):
        """Test getting device information."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Logitech",
            product_name="USB Receiver",
            notes="My mouse receiver"
        )

        device = self.whitelist.get_device("ABC123")

        self.assertIsNotNone(device)
        self.assertEqual(device['serial_number'], "ABC123")
        self.assertEqual(device['vendor_id'], "046d")
        self.assertEqual(device['product_id'], "c52b")
        self.assertEqual(device['vendor_name'], "Logitech")
        self.assertEqual(device['product_name'], "USB Receiver")
        self.assertEqual(device['notes'], "My mouse receiver")
        self.assertIn('added_timestamp', device)
        self.assertIn('use_count', device)

    def test_get_device_not_found(self):
        """Test getting device that doesn't exist."""
        device = self.whitelist.get_device("NONEXISTENT")
        self.assertIsNone(device)

    def test_remove_device(self):
        """Test removing a device from whitelist."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b"
        )

        self.assertTrue(self.whitelist.is_whitelisted("ABC123"))

        result = self.whitelist.remove_device("ABC123")
        self.assertTrue(result)
        self.assertFalse(self.whitelist.is_whitelisted("ABC123"))

    def test_remove_device_not_found(self):
        """Test removing device that doesn't exist."""
        result = self.whitelist.remove_device("NONEXISTENT")
        self.assertFalse(result)

    def test_update_usage(self):
        """Test updating device usage statistics."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b"
        )

        device = self.whitelist.get_device("ABC123")
        self.assertEqual(device['use_count'], 0)
        self.assertIsNone(device['last_used_timestamp'])

        # Update usage
        self.whitelist.update_usage("ABC123")

        device = self.whitelist.get_device("ABC123")
        self.assertEqual(device['use_count'], 1)
        self.assertIsNotNone(device['last_used_timestamp'])

        # Update again
        self.whitelist.update_usage("ABC123")
        device = self.whitelist.get_device("ABC123")
        self.assertEqual(device['use_count'], 2)

    def test_get_all_devices(self):
        """Test getting all whitelisted devices."""
        # Add multiple devices
        for i in range(3):
            self.whitelist.add_device(
                serial_number=f"ABC{i}",
                vendor_id="046d",
                product_id="c52b"
            )

        devices = self.whitelist.get_all_devices()

        self.assertEqual(len(devices), 3)
        self.assertIsInstance(devices, list)
        self.assertIsInstance(devices[0], dict)

    def test_clear_all(self):
        """Test clearing all devices."""
        # Add some devices
        for i in range(3):
            self.whitelist.add_device(
                serial_number=f"ABC{i}",
                vendor_id="046d",
                product_id="c52b"
            )

        self.assertEqual(self.whitelist.get_count(), 3)

        result = self.whitelist.clear_all()
        self.assertTrue(result)
        self.assertEqual(self.whitelist.get_count(), 0)

    def test_get_count(self):
        """Test getting count of whitelisted devices."""
        self.assertEqual(self.whitelist.get_count(), 0)

        self.whitelist.add_device("ABC1", "046d", "c52b")
        self.assertEqual(self.whitelist.get_count(), 1)

        self.whitelist.add_device("ABC2", "046d", "c52b")
        self.assertEqual(self.whitelist.get_count(), 2)

        self.whitelist.remove_device("ABC1")
        self.assertEqual(self.whitelist.get_count(), 1)

    def test_update_device_info(self):
        """Test updating device information."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Old Name",
            notes="Old notes"
        )

        result = self.whitelist.update_device_info(
            serial_number="ABC123",
            vendor_name="New Name",
            notes="New notes"
        )

        self.assertTrue(result)

        device = self.whitelist.get_device("ABC123")
        self.assertEqual(device['vendor_name'], "New Name")
        self.assertEqual(device['notes'], "New notes")

    def test_search_devices(self):
        """Test searching for devices."""
        # Add test devices
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Logitech",
            product_name="Mouse Receiver"
        )

        self.whitelist.add_device(
            serial_number="XYZ789",
            vendor_id="0781",
            product_id="5583",
            vendor_name="SanDisk",
            product_name="USB Drive"
        )

        # Search by vendor
        results = self.whitelist.search_devices("Logitech")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['serial_number'], "ABC123")

        # Search by product
        results = self.whitelist.search_devices("USB Drive")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['serial_number'], "XYZ789")

        # Search by serial
        results = self.whitelist.search_devices("ABC")
        self.assertEqual(len(results), 1)

        # No match
        results = self.whitelist.search_devices("NOMATCH")
        self.assertEqual(len(results), 0)

    def test_search_devices_handles_missing_fields(self):
        """Search should not raise when optional fields are missing."""
        # Simulate a manually edited whitelist entry lacking metadata
        self.whitelist.devices = {
            "ABC123": {
                "serial_number": "ABC123",
                # vendor_name/product_name intentionally omitted
                "notes": None
            }
        }

        # Should return the device when searching by serial despite missing fields
        results = self.whitelist.search_devices("abc")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['serial_number'], "ABC123")

    def test_export_whitelist(self):
        """Test exporting whitelist."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b"
        )

        export_path = self.test_dir / "export.json"
        result = self.whitelist.export_whitelist(export_path)

        self.assertTrue(result)
        self.assertTrue(export_path.exists())

    def test_import_whitelist_replace(self):
        """Test importing whitelist (replace mode)."""
        # Add device to current whitelist
        self.whitelist.add_device("ABC123", "046d", "c52b")

        # Create export from another whitelist
        other_whitelist = DeviceWhitelist(config_dir=Path(tempfile.mkdtemp()))
        other_whitelist.add_device("XYZ789", "0781", "5583")

        export_path = self.test_dir / "export.json"
        other_whitelist.export_whitelist(export_path)

        # Import (replace)
        result = self.whitelist.import_whitelist(export_path, merge=False)
        self.assertTrue(result)

        # Original device should be gone
        self.assertFalse(self.whitelist.is_whitelisted("ABC123"))
        # New device should be present
        self.assertTrue(self.whitelist.is_whitelisted("XYZ789"))

    def test_import_whitelist_merge(self):
        """Test importing whitelist (merge mode)."""
        # Add device to current whitelist
        self.whitelist.add_device("ABC123", "046d", "c52b")

        # Create export from another whitelist
        other_dir = Path(tempfile.mkdtemp())
        try:
            other_whitelist = DeviceWhitelist(config_dir=other_dir)
            other_whitelist.add_device("XYZ789", "0781", "5583")

            export_path = self.test_dir / "export.json"
            other_whitelist.export_whitelist(export_path)

            # Import (merge)
            result = self.whitelist.import_whitelist(export_path, merge=True)
            self.assertTrue(result)

            # Both devices should be present
            self.assertTrue(self.whitelist.is_whitelisted("ABC123"))
            self.assertTrue(self.whitelist.is_whitelisted("XYZ789"))
            self.assertEqual(self.whitelist.get_count(), 2)

        finally:
            shutil.rmtree(other_dir)

    def test_import_whitelist_merge_updates_existing_metadata(self):
        """Merge mode should refresh metadata without clobbering usage stats."""
        self.whitelist.add_device(
            serial_number="ABC123",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Old Name",
            product_name="Old Product",
            notes="Legacy note"
        )

        # Simulate prior usage so there is history to preserve.
        self.whitelist.update_usage("ABC123")
        original = dict(self.whitelist.get_device("ABC123"))

        update_payload = {
            "ABC123": {
                "vendor_id": "9999",
                "product_id": "1111",
                "vendor_name": "New Name",
                "product_name": "New Product",
                "notes": "Updated note"
            }
        }

        update_file = self.test_dir / "update.json"
        update_file.write_text(json.dumps(update_payload))

        self.assertTrue(self.whitelist.import_whitelist(update_file, merge=True))

        refreshed = self.whitelist.get_device("ABC123")
        self.assertEqual(refreshed["vendor_name"], "New Name")
        self.assertEqual(refreshed["product_name"], "New Product")
        self.assertEqual(refreshed["notes"], "Updated note")
        self.assertEqual(refreshed["vendor_id"], "9999")
        self.assertEqual(refreshed["product_id"], "1111")

        # Usage data should remain untouched.
        self.assertEqual(refreshed["use_count"], original["use_count"])
        self.assertEqual(refreshed["last_used_timestamp"], original["last_used_timestamp"])
        self.assertEqual(refreshed["added_timestamp"], original["added_timestamp"])

    def test_import_whitelist_normalizes_partial_entries(self):
        """Imported devices missing metadata should be normalized safely."""
        raw_data = {
            "ABC123": {
                "vendor_id": "046d",
                "product_id": "c52b",
                # optional fields intentionally omitted
            }
        }
        export_path = self.test_dir / "raw.json"
        export_path.write_text(json.dumps(raw_data))

        result = self.whitelist.import_whitelist(export_path, merge=False)
        self.assertTrue(result)

        device = self.whitelist.get_device("ABC123")
        self.assertIsNotNone(device)
        self.assertEqual(device["serial_number"], "ABC123")
        self.assertEqual(device["vendor_name"], "Vendor 046d")
        self.assertEqual(device["product_name"], "Product c52b")
        self.assertEqual(device["use_count"], 0)
        self.assertIsNone(device["last_used_timestamp"])

        # Updating usage should no longer raise due to missing bookkeeping fields.
        self.assertTrue(self.whitelist.update_usage("ABC123"))


class TestDeviceInfo(unittest.TestCase):
    """Test cases for DeviceInfo helper class."""

    def test_parse_device_path(self):
        """Test parsing device ID from path."""
        device_id = DeviceInfo.parse_device_path("/sys/bus/usb/devices/1-4")
        self.assertEqual(device_id, "1-4")

        device_id = DeviceInfo.parse_device_path("/sys/bus/usb/devices/2-1.3")
        self.assertEqual(device_id, "2-1.3")

    def test_parse_device_path_invalid(self):
        """Test parsing invalid device path."""
        device_id = DeviceInfo.parse_device_path("")
        self.assertIsNone(device_id)


if __name__ == '__main__':
    unittest.main()
