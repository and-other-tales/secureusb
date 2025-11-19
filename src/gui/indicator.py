#!/usr/bin/env python3
"""
SecureUSB AppIndicator for GNOME.

Runs as a lightweight Gtk3 application that exposes a tray icon with quick
actions (enable/disable protection, open setup wizard, launch the client) and
reflects the daemon's protection state in real time.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gio

INDICATOR_MODULE = None

for module_name in ('AyatanaAppIndicator3', 'AppIndicator3'):
    try:
        gi.require_version(module_name, '0.1')
        INDICATOR_MODULE = module_name
        break
    except ValueError:
        continue

if INDICATOR_MODULE is None:
    print("Error: Neither AyatanaAppIndicator3 nor AppIndicator3 is available.")
    sys.exit(1)

if INDICATOR_MODULE == 'AyatanaAppIndicator3':
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
else:
    from gi.repository import AppIndicator3

# Ensure repo modules are importable when running from /usr/local/bin wrapper
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.daemon.dbus_service import DBusClient


class SecureUSBIndicator:
    """Encapsulates the AppIndicator menu."""

    def __init__(self):
        self.dbus_client: Optional[DBusClient] = None
        self.enabled = False
        self._updating_toggle = False

        self.indicator = AppIndicator3.Indicator.new(
            "secureusb",
            "secureusb",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.menu = Gtk.Menu()
        self.status_item = Gtk.MenuItem(label="SecureUSB: Initializing…")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)

        self.toggle_item = Gtk.CheckMenuItem(label="Enable Protection")
        self.toggle_item.connect("toggled", self._on_toggle)
        self.menu.append(self.toggle_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.setup_item = Gtk.MenuItem(label="Run Setup Wizard")
        self.setup_item.connect("activate", lambda *_: self._launch_command('secureusb-setup'))
        self.menu.append(self.setup_item)

        self.client_item = Gtk.MenuItem(label="Open Authorization UI")
        self.client_item.connect("activate", lambda *_: self._launch_command('secureusb-client'))
        self.menu.append(self.client_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit Indicator")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(quit_item)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

        GLib.idle_add(self._connect_dbus)
        GLib.timeout_add_seconds(2, self._show_startup_notification)

    def _connect_dbus(self):
        self.dbus_client = DBusClient('system')
        if not self.dbus_client.is_connected():
            self.status_item.set_label("SecureUSB: Daemon unavailable")
            GLib.timeout_add_seconds(5, self._connect_dbus)
            return False

        try:
            enabled = bool(self.dbus_client.interface.IsEnabled())
            self._update_state(enabled)
        except Exception as exc:
            self.status_item.set_label(f"SecureUSB: Error {exc}")

        self.dbus_client.connect_to_signal('ProtectionStateChanged', self._on_protection_changed)
        return False

    def _on_protection_changed(self, enabled):
        self._update_state(bool(enabled))

    def _update_state(self, enabled: bool):
        self.enabled = enabled
        self.status_item.set_label(f"SecureUSB: {'Enabled' if enabled else 'Disabled'}")
        self.indicator.set_icon_full(
            "secureusb" if enabled else "secureusb-disabled",
            "SecureUSB"
        )
        self._updating_toggle = True
        self.toggle_item.set_active(enabled)
        self._updating_toggle = False

    def _on_toggle(self, widget):
        if self._updating_toggle:
            return
        if not self.dbus_client or not self.dbus_client.interface:
            self.toggle_item.set_active(self.enabled)
            return
        new_state = widget.get_active()
        try:
            self.dbus_client.interface.SetEnabled(new_state)
        except Exception as exc:
            print(f"Error toggling protection: {exc}")
            self.toggle_item.set_active(self.enabled)

    @staticmethod
    def _launch_command(command: str):
        try:
            subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            print(f"Failed to launch {command}: {exc}")

    def _show_startup_notification(self):
        """Show a notification on startup to help users find the indicator."""
        try:
            # Check if GNOME Shell is running
            result = subprocess.run(
                ['pgrep', '-x', 'gnome-shell'],
                capture_output=True,
                timeout=1
            )

            if result.returncode == 0:
                # GNOME is running, check for AppIndicator extension
                result = subprocess.run(
                    ['gnome-extensions', 'list', '--enabled'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                # Check for both possible extension IDs
                ext_enabled = False
                if result.returncode == 0:
                    for ext_id in ['ubuntu-appindicators@ubuntu.com', 'appindicatorsupport@rgcjonas.gmail.com']:
                        if ext_id in result.stdout:
                            ext_enabled = True
                            break

                if not ext_enabled:
                    # AppIndicator extension not enabled
                    notification = Gio.Notification.new("SecureUSB Indicator Started")
                    notification.set_body(
                        "The indicator is running, but may not be visible in the top bar.\n"
                        "Modern GNOME requires the AppIndicator extension.\n\n"
                        "Enable it with:\n"
                        "gnome-extensions enable ubuntu-appindicators@ubuntu.com\n\n"
                        "Then restart GNOME Shell (Alt+F2, type 'r', press Enter)"
                    )
                    notification.set_icon(Gio.ThemedIcon.new("secureusb"))

                    app = Gio.Application.get_default()
                    if app:
                        app.send_notification("secureusb-indicator", notification)
                    else:
                        # Fallback: use notify-send if available
                        subprocess.run([
                            'notify-send',
                            '--app-name=SecureUSB',
                            '--icon=secureusb',
                            'SecureUSB Indicator Started',
                            'The indicator is running but may not be visible. '
                            'Enable the extension: gnome-extensions enable ubuntu-appindicators@ubuntu.com'
                        ], timeout=2)
        except Exception:
            pass  # Silently fail - notification is optional

        return False  # Don't repeat the notification


def main():
    SecureUSBIndicator()
    Gtk.main()


if __name__ == "__main__":
    main()
