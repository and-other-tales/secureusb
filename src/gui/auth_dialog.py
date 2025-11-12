#!/usr/bin/env python3
"""
Authorization Dialog for SecureUSB

GTK4 dialog for authorizing USB devices with TOTP authentication.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.daemon.dbus_service import DBusClient


class AuthorizationDialog(Adw.Window):
    """GTK4 dialog for USB device authorization."""

    def __init__(self, device_info: dict, dbus_client: DBusClient):
        """
        Initialize authorization dialog.

        Args:
            device_info: Dictionary with device information
            dbus_client: D-Bus client for communication with daemon
        """
        super().__init__()

        self.device_info = device_info
        self.dbus_client = dbus_client
        self.timeout_seconds = 30
        self.timeout_id = None

        # Configure window
        self.set_title("USB Device Authorization Required")
        self.set_default_size(500, 400)
        self.set_modal(True)
        self.set_deletable(False)  # Force user to make a choice

        # Build UI
        self._build_ui()

        # Start countdown timer
        self._start_countdown()

    def _build_ui(self):
        """Build the dialog UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Header with icon and warning
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        header_box.set_halign(Gtk.Align.CENTER)

        # Warning icon
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("warning")
        header_box.append(icon)

        # Title label
        title_label = Gtk.Label(label="USB Device Connected")
        title_label.add_css_class("title-1")
        header_box.append(title_label)

        main_box.append(header_box)

        # Device information group
        device_group = Adw.PreferencesGroup()
        device_group.set_title("Device Information")

        # Device name
        device_name = self.device_info.get('display_name', 'Unknown Device')
        name_row = Adw.ActionRow(title="Device", subtitle=device_name)
        name_icon = Gtk.Image.new_from_icon_name("drive-removable-media-usb-symbolic")
        name_row.add_prefix(name_icon)
        device_group.add(name_row)

        # Vendor and Product IDs
        ids = f"{self.device_info.get('vendor_id', '????')}:{self.device_info.get('product_id', '????')}"
        ids_row = Adw.ActionRow(title="USB IDs", subtitle=ids)
        ids_icon = Gtk.Image.new_from_icon_name("emblem-system-symbolic")
        ids_row.add_prefix(ids_icon)
        device_group.add(ids_row)

        # Serial number (if available)
        serial = self.device_info.get('serial_number', '')
        if serial:
            serial_row = Adw.ActionRow(title="Serial Number", subtitle=serial)
            serial_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            serial_row.add_prefix(serial_icon)
            device_group.add(serial_row)

        main_box.append(device_group)

        # Authentication group
        auth_group = Adw.PreferencesGroup()
        auth_group.set_title("Authentication")
        auth_group.set_description("Enter your 6-digit TOTP code from Google Authenticator")

        # TOTP entry
        self.totp_entry = Gtk.Entry()
        self.totp_entry.set_placeholder_text("000000")
        self.totp_entry.set_max_length(6)
        self.totp_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        self.totp_entry.set_alignment(0.5)  # Center text
        self.totp_entry.set_width_chars(10)
        self.totp_entry.add_css_class("large-entry")
        self.totp_entry.connect("changed", self._on_totp_changed)
        self.totp_entry.connect("activate", self._on_totp_activate)

        # TOTP entry row
        totp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        totp_box.set_halign(Gtk.Align.CENTER)
        totp_box.append(self.totp_entry)

        # Countdown label
        self.countdown_label = Gtk.Label(label=f"Time remaining: {self.timeout_seconds}s")
        self.countdown_label.add_css_class("dim-label")
        totp_box.append(self.countdown_label)

        auth_group_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        auth_group_box.set_margin_top(10)
        auth_group_box.set_margin_bottom(10)
        auth_group_box.append(totp_box)

        # Add to group using a wrapper
        wrapper_row = Adw.ActionRow()
        wrapper_row.set_child(auth_group_box)
        auth_group.add(wrapper_row)

        main_box.append(auth_group)

        # Whitelist checkbox
        self.whitelist_check = Gtk.CheckButton(label="Remember this device (still requires TOTP)")
        self.whitelist_check.set_halign(Gtk.Align.CENTER)
        self.whitelist_check.set_margin_top(10)
        if not self.device_info.get('serial_number'):
            self.whitelist_check.set_sensitive(False)
            self.whitelist_check.set_tooltip_text("Device has no serial number")
        main_box.append(self.whitelist_check)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(20)

        # Deny button
        deny_button = Gtk.Button(label="Deny")
        deny_button.set_size_request(120, -1)
        deny_button.add_css_class("destructive-action")
        deny_button.connect("clicked", self._on_deny_clicked)
        button_box.append(deny_button)

        # Power-only button
        power_button = Gtk.Button(label="Power Only")
        power_button.set_size_request(120, -1)
        power_button.connect("clicked", self._on_power_only_clicked)
        button_box.append(power_button)

        # Connect button (default)
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.set_size_request(120, -1)
        self.connect_button.add_css_class("suggested-action")
        self.connect_button.set_sensitive(False)  # Disabled until TOTP entered
        self.connect_button.connect("clicked", self._on_connect_clicked)
        button_box.append(self.connect_button)

        main_box.append(button_box)

        # Set window content
        self.set_content(main_box)

        # Focus TOTP entry
        self.totp_entry.grab_focus()

    def _start_countdown(self):
        """Start the countdown timer."""
        self.timeout_id = GLib.timeout_add_seconds(1, self._update_countdown)

    def _update_countdown(self) -> bool:
        """Update countdown timer."""
        self.timeout_seconds -= 1

        if self.timeout_seconds <= 0:
            self.countdown_label.set_text("Time expired! Device denied.")
            self._auto_deny()
            return False  # Stop timer

        # Update label
        self.countdown_label.set_text(f"Time remaining: {self.timeout_seconds}s")

        # Add warning class when time is low
        if self.timeout_seconds <= 10:
            self.countdown_label.add_css_class("error")

        return True  # Continue timer

    def _on_totp_changed(self, entry):
        """Handle TOTP entry changes."""
        text = entry.get_text()

        # Only allow digits
        if text and not text.isdigit():
            entry.set_text(''.join(c for c in text if c.isdigit()))
            return

        # Enable connect button when 6 digits entered
        self.connect_button.set_sensitive(len(text) == 6)

    def _on_totp_activate(self, entry):
        """Handle Enter key in TOTP entry."""
        if len(entry.get_text()) == 6:
            self._on_connect_clicked(None)

    def _on_connect_clicked(self, button):
        """Handle Connect button click."""
        totp_code = self.totp_entry.get_text()

        if len(totp_code) != 6:
            self._show_error("Please enter a 6-digit TOTP code")
            return

        self._authorize_device('full', totp_code)

    def _on_power_only_clicked(self, button):
        """Handle Power Only button click."""
        totp_code = self.totp_entry.get_text()

        if len(totp_code) != 6:
            self._show_error("Please enter a 6-digit TOTP code")
            return

        self._authorize_device('power_only', totp_code)

    def _on_deny_clicked(self, button):
        """Handle Deny button click."""
        self._deny_device()

    def _authorize_device(self, mode: str, totp_code: str):
        """
        Send authorization request to daemon.

        Args:
            mode: 'full' or 'power_only'
            totp_code: TOTP authentication code
        """
        # Stop countdown
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

        # Send authorization request
        result = self.dbus_client.authorize_device(self.device_info, totp_code, mode)

        if result == 'success':
            # Add to whitelist if requested
            if self.whitelist_check.get_active() and self.device_info.get('serial_number'):
                # TODO: Add to whitelist via D-Bus
                pass

            self.close()

        elif result == 'auth_failed':
            self._show_error("Authentication failed. Invalid TOTP code.")
            self.totp_entry.select_region(0, -1)
            self.totp_entry.grab_focus()

            # Restart countdown
            self._start_countdown()

        else:
            self._show_error(f"Authorization error: {result}")

    def _deny_device(self):
        """Deny device authorization."""
        # Stop countdown
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

        # Send deny request
        device_id = self.device_info.get('device_id', '')
        self.dbus_client.deny_device(device_id)

        self.close()

    def _auto_deny(self):
        """Auto-deny device on timeout."""
        GLib.timeout_add(1000, lambda: (self._deny_device(), False))

    def _show_error(self, message: str):
        """
        Show error message.

        Args:
            message: Error message
        """
        # Create error label
        error_label = Gtk.Label(label=message)
        error_label.add_css_class("error")
        error_label.set_wrap(True)

        # TODO: Show as toast notification in Adwaita
        print(f"Error: {message}")


def show_authorization_dialog(device_info: dict):
    """
    Show authorization dialog for a USB device.

    Args:
        device_info: Device information dictionary
    """
    # Connect to D-Bus
    dbus_client = DBusClient('system')

    if not dbus_client.is_connected():
        print("Error: Could not connect to SecureUSB daemon")
        return

    # Create and show dialog
    dialog = AuthorizationDialog(device_info, dbus_client)
    dialog.present()


# Test standalone
if __name__ == "__main__":
    # Test device info
    test_device = {
        'device_id': '1-4',
        'vendor_id': '046d',
        'product_id': 'c52b',
        'vendor_name': 'Logitech',
        'product_name': 'USB Receiver',
        'serial_number': 'ABC123456',
        'display_name': 'Logitech USB Receiver'
    }

    app = Adw.Application(application_id="org.secureusb.AuthDialog.Test")

    def on_activate(app):
        show_authorization_dialog(test_device)

    app.connect('activate', on_activate)
    app.run(None)
