#!/usr/bin/env python3
"""
Logging Module for SecureUSB

Handles event logging to SQLite database for audit trail.
Records all USB device connection attempts and authorization decisions.
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum

from .paths import resolve_config_dir


class EventAction(Enum):
    """Types of USB events to log."""
    DEVICE_CONNECTED = "connected"
    DEVICE_AUTHORIZED = "authorized"
    DEVICE_AUTHORIZED_POWER_ONLY = "authorized_power_only"
    DEVICE_DENIED = "denied"
    DEVICE_DISCONNECTED = "disconnected"
    AUTH_FAILED = "auth_failed"
    AUTH_SUCCESS = "auth_success"
    WHITELIST_ADDED = "whitelist_added"
    WHITELIST_REMOVED = "whitelist_removed"


class USBLogger:
    """Manages logging of USB security events to SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize USB event logger.

        Args:
            db_path: Path to SQLite database. If None, uses the shared SecureUSB config dir.
        """
        if db_path is None:
            config_dir = resolve_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "events.db"
        else:
            self.db_path = Path(db_path)

        self._init_database()

        # Automatically cleanup old events on initialization
        self._auto_cleanup()

    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usb_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                action TEXT NOT NULL,
                device_path TEXT,
                vendor_id TEXT,
                product_id TEXT,
                vendor_name TEXT,
                product_name TEXT,
                serial_number TEXT,
                auth_method TEXT,
                success INTEGER,
                details TEXT
            )
        ''')

        # Create index on timestamp for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON usb_events(timestamp)
        ''')

        # Create index on serial_number for device history
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_serial ON usb_events(serial_number)
        ''')

        conn.commit()
        conn.close()

    def _auto_cleanup(self):
        """Automatically cleanup old events based on default retention policy."""
        try:
            from .config import Config
            config = Config()
            retention_days = config.get('security.log_retention_days', 90)
            deleted_count = self.cleanup_old_events(retention_days)
            if deleted_count > 0:
                print(f"[Logger] Cleaned up {deleted_count} old events (>{retention_days} days)")
        except Exception as e:
            # Don't fail initialization if cleanup fails
            print(f"[Logger] Warning: Auto-cleanup failed: {e}")

    def log_event(self,
                  action: EventAction,
                  device_path: Optional[str] = None,
                  vendor_id: Optional[str] = None,
                  product_id: Optional[str] = None,
                  vendor_name: Optional[str] = None,
                  product_name: Optional[str] = None,
                  serial_number: Optional[str] = None,
                  auth_method: Optional[str] = None,
                  success: Optional[bool] = None,
                  details: Optional[str] = None) -> int:
        """
        Log a USB security event.

        Args:
            action: Type of event (from EventAction enum)
            device_path: System device path (e.g., /sys/bus/usb/devices/1-4)
            vendor_id: USB vendor ID (e.g., "046d")
            product_id: USB product ID (e.g., "c52b")
            vendor_name: Human-readable vendor name
            product_name: Human-readable product name
            serial_number: Device serial number
            auth_method: Authentication method used (totp/recovery/whitelist)
            success: Whether the action succeeded
            details: Additional details or error messages

        Returns:
            Event ID in the database
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO usb_events (
                timestamp, action, device_path, vendor_id, product_id,
                vendor_name, product_name, serial_number, auth_method,
                success, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            time.time(),
            action.value,
            device_path,
            vendor_id,
            product_id,
            vendor_name,
            product_name,
            serial_number,
            auth_method,
            1 if success else 0 if success is not None else None,
            details
        ))

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return event_id

    def get_recent_events(self, limit: int = 100) -> List[Dict]:
        """
        Get recent USB events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM usb_events
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_events_by_date_range(self,
                                   start_timestamp: float,
                                   end_timestamp: float) -> List[Dict]:
        """
        Get events within a date range.

        Args:
            start_timestamp: Start time (Unix timestamp)
            end_timestamp: End time (Unix timestamp)

        Returns:
            List of event dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM usb_events
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        ''', (start_timestamp, end_timestamp))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_device_history(self, serial_number: str) -> List[Dict]:
        """
        Get all events for a specific device.

        Args:
            serial_number: Device serial number

        Returns:
            List of event dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM usb_events
            WHERE serial_number = ?
            ORDER BY timestamp DESC
        ''', (serial_number,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_failed_auth_attempts(self, hours: int = 24) -> List[Dict]:
        """
        Get failed authentication attempts within the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of event dictionaries
        """
        cutoff_time = time.time() - (hours * 3600)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM usb_events
            WHERE action = ? AND timestamp > ? AND success = 0
            ORDER BY timestamp DESC
        ''', (EventAction.AUTH_FAILED.value, cutoff_time))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def cleanup_old_events(self, days: int = 90) -> int:
        """
        Delete events older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of deleted events
        """
        cutoff_time = time.time() - (days * 86400)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM usb_events
            WHERE timestamp < ?
        ''', (cutoff_time,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    def get_statistics(self) -> Dict:
        """
        Get statistics about logged events.

        Returns:
            Dictionary with various statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total events
        cursor.execute('SELECT COUNT(*) FROM usb_events')
        stats['total_events'] = cursor.fetchone()[0]

        # Events by action type
        cursor.execute('''
            SELECT action, COUNT(*) as count
            FROM usb_events
            GROUP BY action
        ''')
        stats['by_action'] = dict(cursor.fetchall())

        # Failed authentications (last 24h)
        cutoff_time = time.time() - 86400
        cursor.execute('''
            SELECT COUNT(*) FROM usb_events
            WHERE action = ? AND timestamp > ? AND success = 0
        ''', (EventAction.AUTH_FAILED.value, cutoff_time))
        stats['failed_auth_24h'] = cursor.fetchone()[0]

        # Unique devices
        cursor.execute('''
            SELECT COUNT(DISTINCT serial_number) FROM usb_events
            WHERE serial_number IS NOT NULL
        ''')
        stats['unique_devices'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def export_to_csv(self, output_path: Path, limit: Optional[int] = None) -> bool:
        """
        Export events to CSV file.

        Args:
            output_path: Path to output CSV file
            limit: Maximum number of events to export (None for all)

        Returns:
            True if successful, False otherwise
        """
        try:
            import csv

            events = self.get_recent_events(limit if limit else 999999)

            with open(output_path, 'w', newline='') as csvfile:
                if not events:
                    return True

                fieldnames = events[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for event in events:
                    # Convert timestamp to readable format
                    event_copy = event.copy()
                    event_copy['timestamp'] = datetime.fromtimestamp(
                        event['timestamp']
                    ).isoformat()
                    writer.writerow(event_copy)

            return True

        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    print("=== SecureUSB Logger Test ===\n")

    logger = USBLogger()

    # Log some test events
    logger.log_event(
        EventAction.DEVICE_CONNECTED,
        device_path="/sys/bus/usb/devices/1-4",
        vendor_id="046d",
        product_id="c52b",
        vendor_name="Logitech",
        product_name="USB Receiver",
        serial_number="ABC123456"
    )

    logger.log_event(
        EventAction.AUTH_SUCCESS,
        serial_number="ABC123456",
        auth_method="totp",
        success=True
    )

    logger.log_event(
        EventAction.DEVICE_AUTHORIZED,
        serial_number="ABC123456",
        success=True
    )

    # Get recent events
    print("Recent Events:")
    events = logger.get_recent_events(10)
    for event in events:
        timestamp = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {timestamp} - {event['action']} - {event['product_name'] or 'N/A'}")

    # Get statistics
    print("\nStatistics:")
    stats = logger.get_statistics()
    print(f"  Total events: {stats['total_events']}")
    print(f"  Unique devices: {stats['unique_devices']}")
    print(f"  Failed auth (24h): {stats['failed_auth_24h']}")

    print(f"\nDatabase location: {logger.db_path}")
