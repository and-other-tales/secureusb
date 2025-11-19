#!/usr/bin/env python3
"""
Setup Wizard for SecureUSB

First-run wizard for configuring TOTP authentication with Google Authenticator.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GdkPixbuf, Pango, GLib

import sys
import qrcode
from io import BytesIO
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.auth import TOTPAuthenticator, RecoveryCodeManager, SecureStorage, create_new_authenticator


class SetupWizard(Adw.Window):
    """Setup wizard for first-time TOTP configuration."""

    def __init__(self):
        """Initialize the setup wizard."""
        super().__init__()

        self.authenticator = None
        self.recovery_codes = []
        self.storage = SecureStorage()
        self._should_show_ui = True

        # Check if already configured
        if self.storage.is_configured():
            print("SecureUSB is already configured!")
            self._should_show_ui = False
            return

        # Configure window
        self.set_title("SecureUSB Setup Wizard")
        self.set_default_size(600, 700)
        self.set_modal(True)
        self.set_deletable(False)

        # Create pages
        self.current_page = 0
        self.pages = [
            self._create_welcome_page(),
            self._create_qr_page(),
            self._create_test_page(),
            self._create_recovery_codes_page(),
            self._create_complete_page()
        ]

        # Main stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        for i, page in enumerate(self.pages):
            self.stack.add_named(page, f"page{i}")

        self.set_content(self.stack)
        self._show_page(0)

    def _create_welcome_page(self):
        """Create the welcome page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_valign(Gtk.Align.CENTER)

        # Icon
        icon = Gtk.Image.new_from_icon_name("security-high-symbolic")
        icon.set_pixel_size(96)
        box.append(icon)

        # Title
        title = Gtk.Label(label="Welcome to SecureUSB")
        title.add_css_class("title-1")
        box.append(title)

        # Description
        desc = Gtk.Label(label="Protect your computer from unauthorized USB devices")
        desc.add_css_class("dim-label")
        box.append(desc)

        # Information
        info_text = """
SecureUSB blocks all USB devices by default and requires
your approval before any device can access your computer.

You'll use Google Authenticator (or any TOTP app) on your
phone to generate authentication codes.

This setup wizard will guide you through the configuration.
        """

        info_label = Gtk.Label(label=info_text.strip())
        info_label.set_wrap(True)
        info_label.set_justify(Gtk.Justification.CENTER)
        info_label.set_margin_top(20)
        box.append(info_label)

        # Next button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(30)

        next_button = Gtk.Button(label="Get Started")
        next_button.add_css_class("suggested-action")
        next_button.add_css_class("pill")
        next_button.set_size_request(150, -1)
        next_button.connect("clicked", lambda b: self._next_page())
        button_box.append(next_button)

        box.append(button_box)

        return box

    def _create_qr_page(self):
        """Create the QR code page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        # Title
        title = Gtk.Label(label="Scan QR Code")
        title.add_css_class("title-2")
        box.append(title)

        # Instructions
        instructions = """
1. Install Google Authenticator (or any TOTP app) on your phone
2. Open the app and tap '+' to add a new account
3. Select 'Scan QR code'
4. Scan the QR code below

You'll verify it's working on the next screen.
        """

        inst_label = Gtk.Label(label=instructions.strip())
        inst_label.set_wrap(True)
        inst_label.set_justify(Gtk.Justification.LEFT)
        box.append(inst_label)

        # QR code image
        self.qr_image = Gtk.Image()
        self.qr_image.set_pixel_size(300)
        box.append(self.qr_image)

        # Manual entry option
        expander = Gtk.Expander(label="Can't scan? Enter manually")
        expander_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        expander_box.set_margin_top(10)
        expander_box.set_margin_bottom(10)

        self.secret_label = Gtk.Label()
        self.secret_label.set_selectable(True)
        self.secret_label.add_css_class("monospace")
        expander_box.append(self.secret_label)

        copy_button = Gtk.Button(label="Copy to Clipboard")
        copy_button.connect("clicked", self._on_copy_secret)
        expander_box.append(copy_button)

        expander.set_child(expander_box)
        box.append(expander)

        # Navigation buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(20)

        back_button = Gtk.Button(label="Back")
        back_button.connect("clicked", lambda b: self._previous_page())
        button_box.append(back_button)

        next_button = Gtk.Button(label="Next")
        next_button.add_css_class("suggested-action")
        next_button.connect("clicked", lambda b: self._next_page())
        button_box.append(next_button)

        box.append(button_box)

        return box

    def _create_recovery_codes_page(self):
        """Create the recovery codes page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)

        # Title
        title = Gtk.Label(label="Save Your Recovery Codes")
        title.add_css_class("title-2")
        box.append(title)

        # Info text
        info_text = Gtk.Label(
            label="Great! Your authenticator is working correctly.\n\nNow save these backup recovery codes:"
        )
        info_text.set_wrap(True)
        info_text.set_justify(Gtk.Justification.CENTER)
        info_text.set_margin_bottom(10)
        box.append(info_text)

        # Warning
        warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        warning_box.add_css_class("card")
        warning_box.set_margin_top(10)
        warning_box.set_margin_bottom(10)

        warning_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warning_icon.set_margin_start(10)
        warning_box.append(warning_icon)

        warning_text = Gtk.Label(
            label="Save these codes in a safe place!\nYou can use them if you lose access to your authenticator app."
        )
        warning_text.set_wrap(True)
        warning_text.set_margin_top(10)
        warning_text.set_margin_bottom(10)
        warning_text.set_margin_end(10)
        warning_box.append(warning_text)

        box.append(warning_box)

        # Recovery codes display
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_min_content_height(200)

        self.codes_textview = Gtk.TextView()
        self.codes_textview.set_editable(False)
        self.codes_textview.set_monospace(True)
        self.codes_textview.set_wrap_mode(Gtk.WrapMode.NONE)
        self.codes_textview.set_left_margin(20)
        self.codes_textview.set_right_margin(20)
        self.codes_textview.set_top_margin(20)
        self.codes_textview.set_bottom_margin(20)

        scroll.set_child(self.codes_textview)
        box.append(scroll)

        # Copy button
        copy_button = Gtk.Button(label="Copy All Codes")
        copy_button.set_halign(Gtk.Align.CENTER)
        copy_button.connect("clicked", self._on_copy_recovery_codes)
        box.append(copy_button)

        # Confirmation checkbox
        self.saved_check = Gtk.CheckButton(label="I have saved these recovery codes in a safe place")
        self.saved_check.set_halign(Gtk.Align.CENTER)
        self.saved_check.set_margin_top(10)
        box.append(self.saved_check)

        # Navigation buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(20)

        back_button = Gtk.Button(label="Back")
        back_button.connect("clicked", lambda b: self._previous_page())
        button_box.append(back_button)

        self.recovery_next_button = Gtk.Button(label="Next")
        self.recovery_next_button.add_css_class("suggested-action")
        self.recovery_next_button.set_sensitive(False)
        self.recovery_next_button.connect("clicked", lambda b: self._save_and_complete())
        button_box.append(self.recovery_next_button)

        # Enable next button when checkbox is checked
        self.saved_check.connect("toggled", lambda cb: self.recovery_next_button.set_sensitive(cb.get_active()))

        box.append(button_box)

        return box

    def _create_test_page(self):
        """Create the TOTP test page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_valign(Gtk.Align.CENTER)

        # Title
        title = Gtk.Label(label="Verify Your Authenticator")
        title.add_css_class("title-2")
        box.append(title)

        # Instructions
        instructions = Gtk.Label(
            label="Enter the 6-digit code from your authenticator app to verify it's working correctly.\n\nAfter verification, you'll receive backup recovery codes."
        )
        instructions.set_wrap(True)
        instructions.set_justify(Gtk.Justification.CENTER)
        box.append(instructions)

        # TOTP entry
        self.test_entry = Gtk.Entry()
        self.test_entry.set_placeholder_text("000000")
        self.test_entry.set_max_length(6)
        self.test_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        self.test_entry.set_alignment(0.5)
        self.test_entry.set_width_chars(10)
        self.test_entry.add_css_class("large-entry")
        self.test_entry.set_halign(Gtk.Align.CENTER)
        self.test_entry.connect("activate", lambda e: self._test_code())
        box.append(self.test_entry)

        # Result label
        self.test_result_label = Gtk.Label()
        self.test_result_label.set_margin_top(10)
        box.append(self.test_result_label)

        # Navigation buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(30)

        back_button = Gtk.Button(label="Back")
        back_button.connect("clicked", lambda b: self._previous_page())
        button_box.append(back_button)

        test_button = Gtk.Button(label="Verify Code")
        test_button.add_css_class("suggested-action")
        test_button.connect("clicked", lambda b: self._test_code())
        button_box.append(test_button)

        box.append(button_box)

        return box

    def _create_complete_page(self):
        """Create the completion page."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_margin_top(40)
        box.set_margin_bottom(40)
        box.set_margin_start(40)
        box.set_margin_end(40)
        box.set_valign(Gtk.Align.CENTER)

        # Success icon
        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_pixel_size(96)
        icon.add_css_class("success")
        box.append(icon)

        # Title
        title = Gtk.Label(label="Setup Complete!")
        title.add_css_class("title-1")
        box.append(title)

        # Description
        desc_text = """
SecureUSB is now protecting your computer.

When you plug in a USB device, you'll see an authorization
dialog. Enter your TOTP code to allow the device to connect.

The daemon has been enabled and will start automatically
on boot.
        """

        desc = Gtk.Label(label=desc_text.strip())
        desc.set_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        box.append(desc)

        # Finish button
        finish_button = Gtk.Button(label="Finish")
        finish_button.add_css_class("suggested-action")
        finish_button.add_css_class("pill")
        finish_button.set_size_request(150, -1)
        finish_button.set_halign(Gtk.Align.CENTER)
        finish_button.set_margin_top(30)
        finish_button.connect("clicked", lambda b: self._finish_setup())
        box.append(finish_button)

        return box

    def _show_page(self, page_num: int):
        """Show a specific page."""
        if page_num < 0 or page_num >= len(self.pages):
            return

        self.current_page = page_num

        # Generate TOTP on QR page
        if page_num == 1 and not self.authenticator:
            self._generate_totp()

        self.stack.set_visible_child_name(f"page{page_num}")

    def _next_page(self):
        """Go to next page."""
        self._show_page(self.current_page + 1)

    def _previous_page(self):
        """Go to previous page."""
        self._show_page(self.current_page - 1)

    def _generate_totp(self):
        """Generate TOTP secret and QR code."""
        print("Generating TOTP configuration...")

        try:
            # Create authenticator and recovery codes
            self.authenticator, self.recovery_codes = create_new_authenticator()

            # Generate QR code
            uri = self.authenticator.get_provisioning_uri("SecureUSB")

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(uri)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to GdkPixbuf
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            loader = GdkPixbuf.PixbufLoader.new_with_type('png')
            loader.write(buffer.read())
            loader.close()

            pixbuf = loader.get_pixbuf()
            self.qr_image.set_from_pixbuf(pixbuf)

        except Exception as e:
            print(f"Error generating QR code: {e}")
            # Show error message to user
            error_label = Gtk.Label(label=f"Error generating QR code: {e}\nPlease use manual entry below.")
            error_label.add_css_class("error")
            error_label.set_wrap(True)
            # QR image will remain empty, user can use manual entry

        # Set secret text
        secret = self.authenticator.get_secret()
        formatted_secret = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])
        self.secret_label.set_text(formatted_secret)

        # Set recovery codes
        buffer = self.codes_textview.get_buffer()
        codes_text = '\n'.join([f"{i:2d}. {code}" for i, code in enumerate(self.recovery_codes, 1)])
        buffer.set_text(codes_text)

    def _clear_clipboard_after_timeout(self, timeout_seconds: int = 30):
        """Clear clipboard after timeout for security."""
        def clear_clipboard():
            clipboard = self.get_clipboard()
            clipboard.set("")  # Clear clipboard
            print("Clipboard cleared for security")
            return False  # Don't repeat

        GLib.timeout_add_seconds(timeout_seconds, clear_clipboard)

    def _on_copy_secret(self, button):
        """Copy secret to clipboard (will be cleared after 30 seconds)."""
        secret = self.authenticator.get_secret()
        clipboard = self.get_clipboard()
        clipboard.set(secret)
        print("Secret copied to clipboard (will be cleared in 30 seconds)")
        self._clear_clipboard_after_timeout(30)

    def _on_copy_recovery_codes(self, button):
        """Copy recovery codes to clipboard (will be cleared after 60 seconds)."""
        codes_text = '\n'.join(self.recovery_codes)
        clipboard = self.get_clipboard()
        clipboard.set(codes_text)
        print("Recovery codes copied to clipboard (will be cleared in 60 seconds)")
        self._clear_clipboard_after_timeout(60)  # Longer timeout for recovery codes

    def _test_code(self):
        """Test TOTP code."""
        code = self.test_entry.get_text()

        if len(code) != 6:
            self.test_result_label.set_text("Please enter a 6-digit code")
            self.test_result_label.remove_css_class("success")
            self.test_result_label.add_css_class("error")
            return

        if self.authenticator.verify_code(code):
            self.test_result_label.set_text("✓ Code verified successfully!")
            self.test_result_label.remove_css_class("error")
            self.test_result_label.add_css_class("success")

            # Go to recovery codes page (configuration will be saved after codes are shown)
            self._next_page()

        else:
            self.test_result_label.set_text("✗ Invalid code. Please try again.")
            self.test_result_label.remove_css_class("success")
            self.test_result_label.add_css_class("error")
            self.test_entry.select_region(0, -1)

    def _save_configuration(self):
        """Save TOTP configuration to storage."""
        print("Saving TOTP configuration...")

        # Hash recovery codes for storage
        hashed_codes = [RecoveryCodeManager.hash_code(code) for code in self.recovery_codes]

        # Save to encrypted storage
        if self.storage.save_auth_data(self.authenticator.get_secret(), hashed_codes):
            print("✓ Configuration saved successfully")
        else:
            print("✗ Error saving configuration")

    def _save_and_complete(self):
        """Save configuration and proceed to completion page."""
        self._save_configuration()
        self._next_page()

    def _finish_setup(self):
        """Finish setup and close wizard."""
        print("Setup wizard complete!")
        self.close()


def run_setup_wizard():
    """Run the setup wizard."""
    app = Adw.Application(application_id="org.secureusb.SetupWizard")

    def on_activate(app):
        wizard = SetupWizard()
        if not getattr(wizard, "_should_show_ui", True):
            print("Close the wizard window or run `secureusb-setup --reset` to reconfigure.")
            app.quit()
            return
        wizard.set_application(app)
        wizard.present()

    app.connect('activate', on_activate)
    app.run(None)


if __name__ == "__main__":
    run_setup_wizard()
