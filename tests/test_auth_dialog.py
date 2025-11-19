#!/usr/bin/env python3
"""
Unit tests for AuthorizationDialog helper logic.

These tests focus on the countdown/auto-deny behavior without needing a
real GTK/Adwaita environment by providing light-weight stubs.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import gi_stubs

gi_stubs.install()

from src.gui.auth_dialog import AuthorizationDialog  # noqa: E402


class TestAuthorizationDialogAutoDeny(unittest.TestCase):
    """Verify that auto-deny scheduling behaves correctly."""

    def setUp(self):
        """Create dialog instance with UI/start timers stubbed out."""
        self.build_patch = patch.object(AuthorizationDialog, "_build_ui", return_value=None)
        self.start_patch = patch.object(AuthorizationDialog, "_start_countdown", return_value=None)
        self.build_patch.start()
        self.start_patch.start()

        device_info = {"device_id": "1-1"}
        self.dialog = AuthorizationDialog(device_info, dbus_client=MagicMock())

        # Replace deny handler so we can assert call counts.
        self.dialog._deny_device = MagicMock()
        self.dialog.whitelist_check = MagicMock()
        self.dialog.whitelist_check.get_active.return_value = False
        self.dialog.close = MagicMock()

    def tearDown(self):
        """Stop patches."""
        self.build_patch.stop()
        self.start_patch.stop()

    def test_auto_deny_runs_once(self):
        """_auto_deny should schedule a single callback that returns False."""
        captured_callback = {}

        def fake_timeout(interval, callback):
            captured_callback["func"] = callback
            captured_callback["interval"] = interval
            return 123

        with patch("src.gui.auth_dialog.GLib.timeout_add", side_effect=fake_timeout) as mock_timeout:
            self.dialog._auto_deny()

            mock_timeout.assert_called_once()
            self.assertEqual(captured_callback["interval"], 1000)

        callback = captured_callback["func"]
        self.assertIsNotNone(callback)

        # Execute callback and ensure it stops the timer and denies once.
        result = callback()
        self.dialog._deny_device.assert_called_once_with()
        self.assertFalse(result)

    def test_authorize_cancels_pending_auto_deny_timer(self):
        """Manual authorization should cancel the scheduled auto-deny callback."""
        self.dialog.auto_deny_id = 321
        self.dialog.timeout_id = None
        self.dialog.dbus_client.authorize_device.return_value = 'success'

        with patch("src.gui.auth_dialog.GLib.source_remove") as mock_remove:
            self.dialog._authorize_device('full', '123456')

        mock_remove.assert_called_once_with(321)
        self.assertIsNone(self.dialog.auto_deny_id)
        self.dialog.dbus_client.authorize_device.assert_called_once()
        self.dialog.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
