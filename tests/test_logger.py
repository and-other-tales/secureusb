#!/usr/bin/env python3
"""
Unit tests for logger module.
"""

import unittest
import tempfile
import time
from pathlib import Path
from datetime import datetime
from src.utils.logger import USBLogger, EventAction


class TestUSBLogger(unittest.TestCase):
    """Test cases for USBLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary database
        self.test_db = Path(tempfile.mktemp(suffix='.db'))
        self.logger = USBLogger(db_path=self.test_db)

    def tearDown(self):
        """Clean up test fixtures."""
        if self.test_db.exists():
            self.test_db.unlink()

    def test_initialization(self):
        """Test logger initialization."""
        self.assertTrue(self.test_db.exists())

    def test_log_event_basic(self):
        """Test logging a basic event."""
        event_id = self.logger.log_event(
            EventAction.DEVICE_CONNECTED,
            device_path="/sys/bus/usb/devices/1-4",
            vendor_id="046d",
            product_id="c52b"
        )

        self.assertIsInstance(event_id, int)
        self.assertGreater(event_id, 0)

    def test_log_event_full(self):
        """Test logging an event with all fields."""
        event_id = self.logger.log_event(
            EventAction.DEVICE_AUTHORIZED,
            device_path="/sys/bus/usb/devices/1-4",
            vendor_id="046d",
            product_id="c52b",
            vendor_name="Logitech",
            product_name="USB Receiver",
            serial_number="ABC123",
            auth_method="totp",
            success=True,
            details="Test authorization"
        )

        self.assertGreater(event_id, 0)

    def test_get_recent_events(self):
        """Test retrieving recent events."""
        # Log some events
        for i in range(5):
            self.logger.log_event(
                EventAction.DEVICE_CONNECTED,
                device_path=f"/sys/bus/usb/devices/1-{i}",
                vendor_id="046d",
                product_id="c52b"
            )

        events = self.logger.get_recent_events(limit=10)

        self.assertEqual(len(events), 5)
        self.assertIsInstance(events[0], dict)

        # Events should be in reverse chronological order (newest first)
        for i in range(len(events) - 1):
            self.assertGreaterEqual(events[i]['timestamp'], events[i + 1]['timestamp'])

    def test_get_recent_events_limit(self):
        """Test that limit parameter works correctly."""
        # Log 10 events
        for i in range(10):
            self.logger.log_event(
                EventAction.DEVICE_CONNECTED,
                device_path=f"/sys/bus/usb/devices/1-{i}"
            )

        events = self.logger.get_recent_events(limit=5)
        self.assertEqual(len(events), 5)

    def test_get_events_by_date_range(self):
        """Test retrieving events by date range."""
        start_time = time.time()

        # Log some events
        for i in range(3):
            self.logger.log_event(
                EventAction.DEVICE_CONNECTED,
                device_path=f"/sys/bus/usb/devices/1-{i}"
            )
            time.sleep(0.1)

        end_time = time.time()

        events = self.logger.get_events_by_date_range(start_time - 1, end_time + 1)
        self.assertEqual(len(events), 3)

        # Test with narrow range (should get 0 events)
        events = self.logger.get_events_by_date_range(0, start_time - 1)
        self.assertEqual(len(events), 0)

    def test_get_device_history(self):
        """Test getting history for a specific device."""
        serial = "ABC123"

        # Log events for this device
        for action in [EventAction.DEVICE_CONNECTED, EventAction.DEVICE_AUTHORIZED, EventAction.DEVICE_DISCONNECTED]:
            self.logger.log_event(
                action,
                serial_number=serial
            )

        # Log event for different device
        self.logger.log_event(
            EventAction.DEVICE_CONNECTED,
            serial_number="XYZ789"
        )

        history = self.logger.get_device_history(serial)

        self.assertEqual(len(history), 3)
        for event in history:
            self.assertEqual(event['serial_number'], serial)

    def test_get_failed_auth_attempts(self):
        """Test getting failed authentication attempts."""
        # Log successful auth
        self.logger.log_event(
            EventAction.AUTH_SUCCESS,
            serial_number="ABC123",
            success=True
        )

        # Log failed auths
        for i in range(3):
            self.logger.log_event(
                EventAction.AUTH_FAILED,
                serial_number="ABC123",
                success=False
            )

        failed = self.logger.get_failed_auth_attempts(hours=24)

        self.assertEqual(len(failed), 3)
        for event in failed:
            self.assertEqual(event['action'], EventAction.AUTH_FAILED.value)
            self.assertEqual(event['success'], 0)

    def test_cleanup_old_events(self):
        """Test cleaning up old events."""
        # Log some events
        for i in range(5):
            self.logger.log_event(
                EventAction.DEVICE_CONNECTED,
                device_path=f"/sys/bus/usb/devices/1-{i}"
            )

        # Cleanup events older than 0 days (should delete all)
        deleted = self.logger.cleanup_old_events(days=0)
        self.assertEqual(deleted, 5)

        # Verify events are gone
        events = self.logger.get_recent_events()
        self.assertEqual(len(events), 0)

    def test_get_statistics(self):
        """Test getting statistics."""
        # Log various events
        self.logger.log_event(EventAction.DEVICE_CONNECTED, serial_number="ABC123")
        self.logger.log_event(EventAction.DEVICE_AUTHORIZED, serial_number="ABC123")
        self.logger.log_event(EventAction.DEVICE_CONNECTED, serial_number="XYZ789")
        self.logger.log_event(EventAction.AUTH_FAILED, success=False)

        stats = self.logger.get_statistics()

        self.assertIn('total_events', stats)
        self.assertEqual(stats['total_events'], 4)

        self.assertIn('by_action', stats)
        self.assertIsInstance(stats['by_action'], dict)

        self.assertIn('unique_devices', stats)
        self.assertEqual(stats['unique_devices'], 2)

    def test_export_to_csv(self):
        """Test exporting events to CSV."""
        # Log some events
        for i in range(3):
            self.logger.log_event(
                EventAction.DEVICE_CONNECTED,
                device_path=f"/sys/bus/usb/devices/1-{i}",
                vendor_id="046d",
                product_id="c52b"
            )

        csv_path = Path(tempfile.mktemp(suffix='.csv'))
        try:
            result = self.logger.export_to_csv(csv_path)
            self.assertTrue(result)
            self.assertTrue(csv_path.exists())

            # Read and verify CSV
            with open(csv_path, 'r') as f:
                content = f.read()
                self.assertIn('timestamp', content)
                self.assertIn('action', content)
                self.assertIn('connected', content)

        finally:
            if csv_path.exists():
                csv_path.unlink()

    def test_event_action_enum(self):
        """Test EventAction enum values."""
        self.assertEqual(EventAction.DEVICE_CONNECTED.value, "connected")
        self.assertEqual(EventAction.DEVICE_AUTHORIZED.value, "authorized")
        self.assertEqual(EventAction.DEVICE_DENIED.value, "denied")
        self.assertEqual(EventAction.AUTH_FAILED.value, "auth_failed")


if __name__ == '__main__':
    unittest.main()
