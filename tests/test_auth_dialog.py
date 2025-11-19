#!/usr/bin/env python3
"""
Unit tests for AuthorizationDialog helper logic.

These tests focus on the countdown/auto-deny behavior without needing a
real GTK/Adwaita environment by providing light-weight stubs.
"""

import sys
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Provide lightweight GI stubs so src.gui.auth_dialog can be imported.
# ---------------------------------------------------------------------------

# Create stub modules for gi.repository.*
gtk_stub = types.ModuleType("Gtk")
adw_stub = types.ModuleType("Adw")
glib_stub = types.ModuleType("GLib")
pango_stub = types.ModuleType("Pango")
gdkpixbuf_stub = types.ModuleType("GdkPixbuf")
gio_stub = types.ModuleType("Gio")

# Provide default no-op implementations for GLib functions that are patched in tests.
glib_stub.timeout_add = lambda *args, **kwargs: None
glib_stub.timeout_add_seconds = lambda *args, **kwargs: None
glib_stub.source_remove = lambda *args, **kwargs: None


class _DummyWindow:
    """Minimal stand-in for Adw.Window used by AuthorizationDialog."""

    def __init__(self, *args, **kwargs):
        pass

    def set_title(self, *args, **kwargs):
        pass

    def set_default_size(self, *args, **kwargs):
        pass

    def set_modal(self, *args, **kwargs):
        pass

    def set_deletable(self, *args, **kwargs):
        pass

    def set_content(self, *args, **kwargs):
        pass

    def close(self):
        pass


adw_stub.Window = _DummyWindow


class _DummyToastOverlay:
    """Minimal toast overlay implementation."""

    def __init__(self):
        self.child = None
        self.toasts = []

    def set_child(self, child):
        self.child = child

    def add_toast(self, toast):
        self.toasts.append(toast)


class _DummyToast:
    """Minimal Adw.Toast stub."""

    def __init__(self, message):
        self.message = message

    @classmethod
    def new(cls, message):
        return cls(message)

    def set_priority(self, priority):
        self.priority = priority

    def set_timeout(self, timeout):
        self.timeout = timeout


class _DummyToastPriority:
    HIGH = 1
    NORMAL = 0


adw_stub.ToastOverlay = _DummyToastOverlay
adw_stub.Toast = _DummyToast
adw_stub.ToastPriority = _DummyToastPriority


class _DummyApplication:
    """Minimal stand-in for Adw.Application used by SecureUSBClient."""

    def __init__(self, *args, **kwargs):
        pass

    def connect(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        return 0

    def quit(self):
        pass

    def send_notification(self, *args, **kwargs):
        pass


adw_stub.Application = _DummyApplication


class _DummyNotification:
    def __init__(self, summary):
        self.summary = summary
        self.body = ""
        self.icon = None

    @classmethod
    def new(cls, summary):
        return cls(summary)

    def set_body(self, body):
        self.body = body

    def set_icon(self, icon):
        self.icon = icon


class _DummyThemedIcon:
    def __init__(self, name):
        self.name = name

    @classmethod
    def new(cls, name):
        return cls(name)


gio_stub.Notification = _DummyNotification
gio_stub.ThemedIcon = _DummyThemedIcon

# Register modules so "from gi.repository import Gtk, Adw, GLib, Pango" works
gi_repo_module = types.ModuleType("gi.repository")
gi_repo_module.Gtk = gtk_stub
gi_repo_module.Adw = adw_stub
gi_repo_module.GLib = glib_stub
gi_repo_module.Pango = pango_stub
gi_repo_module.GdkPixbuf = gdkpixbuf_stub
gi_repo_module.Gio = gio_stub

gi_module = types.ModuleType("gi")
gi_module.repository = gi_repo_module
gi_module.require_version = lambda *args, **kwargs: None

sys.modules["gi"] = gi_module
sys.modules["gi.repository"] = gi_repo_module
sys.modules["gi.repository.Gtk"] = gtk_stub
sys.modules["gi.repository.Adw"] = adw_stub
sys.modules["gi.repository.GLib"] = glib_stub
sys.modules["gi.repository.Pango"] = pango_stub
sys.modules["gi.repository.GdkPixbuf"] = gdkpixbuf_stub
sys.modules["gi.repository.Gio"] = gio_stub


# Ensure repo root is on sys.path for src imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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


if __name__ == "__main__":
    unittest.main()
