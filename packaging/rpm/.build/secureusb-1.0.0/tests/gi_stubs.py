"""Lightweight GI/GTK stubs for headless tests.

Installing these stubs makes modules that require Gtk/Adw/GLib/Gio importable
inside CI environments where the real GObject stack is unavailable. The goal is
to exercise logic without rendering any UI.
"""

from __future__ import annotations

import sys
import types


def _new_dummy_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    return module


def install() -> None:
    """Register stub modules if GI is unavailable."""
    if "gi" in sys.modules:
        # Real GI (or another stub) already loaded; don't override it.
        return

    gtk = _new_dummy_module("Gtk")
    adw = _new_dummy_module("Adw")
    glib = _new_dummy_module("GLib")
    pango = _new_dummy_module("Pango")
    gdkpixbuf = _new_dummy_module("GdkPixbuf")
    gio = _new_dummy_module("Gio")

    class _DummyWindow:
        def __init__(self, *args, **kwargs):
            self._props = {}

        def __getattr__(self, item):
            def _method(*args, **kwargs):
                return None

            return _method

        def set_title(self, *args, **kwargs):
            self._props["title"] = args[0] if args else None

        def set_content(self, *args, **kwargs):
            self._props["content"] = args[0] if args else None

    class _DummyApplication:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            return None

        def run(self, *args, **kwargs):
            return 0

        def quit(self):
            return None

        def send_notification(self, *args, **kwargs):
            return None

    class _DummyToastOverlay:
        def __init__(self):
            self.child = None
            self.toasts = []

        def set_child(self, child):
            self.child = child

        def add_toast(self, toast):
            self.toasts.append(toast)

    class _DummyToast:
        def __init__(self, message):
            self.message = message
            self.priority = None
            self.timeout = None

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

    adw.Window = _DummyWindow
    adw.Application = _DummyApplication
    adw.ToastOverlay = _DummyToastOverlay
    adw.Toast = _DummyToast
    adw.ToastPriority = _DummyToastPriority

    def _noop_timer(*args, **kwargs):
        # Return value mimics GLib source-id handles.
        return object()

    def _noop_remove(*args, **kwargs):
        return None

    glib.timeout_add = _noop_timer
    glib.timeout_add_seconds = _noop_timer
    glib.source_remove = _noop_remove

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

    gio.Notification = _DummyNotification
    gio.ThemedIcon = _DummyThemedIcon

    gi_repo = types.ModuleType("gi.repository")
    gi_repo.Gtk = gtk
    gi_repo.Adw = adw
    gi_repo.GLib = glib
    gi_repo.Pango = pango
    gi_repo.GdkPixbuf = gdkpixbuf
    gi_repo.Gio = gio

    gi_module = types.ModuleType("gi")
    gi_module.repository = gi_repo
    gi_module.require_version = lambda *args, **kwargs: None

    sys.modules["gi"] = gi_module
    sys.modules["gi.repository"] = gi_repo
    sys.modules["gi.repository.Gtk"] = gtk
    sys.modules["gi.repository.Adw"] = adw
    sys.modules["gi.repository.GLib"] = glib
    sys.modules["gi.repository.Pango"] = pango
    sys.modules["gi.repository.GdkPixbuf"] = gdkpixbuf
    sys.modules["gi.repository.Gio"] = gio


__all__ = ["install"]

