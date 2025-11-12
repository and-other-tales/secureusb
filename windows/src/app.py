#!/usr/bin/env python3
"""
SecureUSB Windows 11 port.

Runs as a user-level PySide6 application that monitors USB connections,
blocks them via pnputil until the user completes TOTP authentication,
and logs all activity to the shared SecureUSB database.
"""

from __future__ import annotations

import signal
import sys
from typing import Dict, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from . import path_setup  # noqa: F401
from ports.shared import AuthorizationDialog
from src.auth import RecoveryCodeManager, SecureStorage, TOTPAuthenticator
from src.daemon.authorization import AuthorizationMode
from src.utils import Config, DeviceWhitelist, EventAction, USBLogger

from .usb_blocker import WindowsDeviceBlocker
from .usb_monitor import WindowsUSBDevice, WindowsUSBMonitor


class SecureUSBWindowsApp(QApplication):
    """Main application class."""

    def __init__(self):
        super().__init__(sys.argv)
        self.setQuitOnLastWindowClosed(False)

        self.config = Config()
        self.logger = USBLogger()
        self.whitelist = DeviceWhitelist()
        self.storage = SecureStorage()
        self.totp_auth: Optional[TOTPAuthenticator] = None
        self.recovery_codes = []

        if not self._load_authentication():
            print("SecureUSB is not configured. Run windows/src/setup_cli.py first.")
            sys.exit(1)

        self.monitor = WindowsUSBMonitor()
        self.event_poller = QTimer()
        self.event_poller.setInterval(400)
        self.event_poller.timeout.connect(self._drain_events)

        self.pending: Dict[str, Dict] = {}

        self.aboutToQuit.connect(self._cleanup)
        signal.signal(signal.SIGINT, lambda *_: self.quit())

    def start(self):
        self.monitor.start()
        self.event_poller.start()
        print("SecureUSB Windows client running. Press Ctrl+C to exit.")
        sys.exit(self.exec())

    def _cleanup(self):
        self.monitor.stop()
        for pending in self.pending.values():
            timer = pending.get("timer")
            if isinstance(timer, QTimer):
                timer.stop()
            dialog = pending.get("dialog")
            if dialog:
                dialog.close()

    def _load_authentication(self) -> bool:
        if not self.storage.is_configured():
            return False

        data = self.storage.load_auth_data()
        if not data:
            return False

        self.totp_auth = TOTPAuthenticator(data["totp_secret"])
        self.recovery_codes = list(data.get("recovery_codes", []))
        return True

    def _drain_events(self):
        for action, device in self.monitor.get_events():
            if action == "add":
                self._handle_device_connected(device)
            elif action == "remove":
                self._handle_device_removed(device)

    def _handle_device_connected(self, device: WindowsUSBDevice):
        info = device.to_dict()
        print(f"[SecureUSB] Device connected: {info['display_name']}")

        self.logger.log_event(
            EventAction.DEVICE_CONNECTED,
            vendor_id=info.get("vendor_id"),
            product_id=info.get("product_id"),
            product_name=info.get("display_name"),
            serial_number=info.get("serial_number"),
            device_path=info.get("instance_id"),
        )

        if not self.config.is_enabled():
            print("[SecureUSB] Protection disabled, skipping authorization.")
            return

        if not self.totp_auth:
            print("[SecureUSB] TOTP is not configured, skipping authorization.")
            return

        WindowsDeviceBlocker.block_device(device.instance_id)
        timeout_seconds = self.config.get_timeout()
        dialog = AuthorizationDialog(
            device_info=info,
            timeout_seconds=timeout_seconds,
            on_submit=lambda mode, code, remember: self._authorize_device(device, mode, code, remember),
            on_power_only=lambda mode, code, remember: self._authorize_device(device, mode, code, remember),
            on_deny=lambda auto: self._deny_device(device, auto),
        )
        dialog.show()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda dev_id=device.device_id: self._handle_timeout(dev_id))
        timer.start(timeout_seconds * 1000)

        self.pending[device.device_id] = {
            "device": device,
            "dialog": dialog,
            "timer": timer,
        }

    def _handle_device_removed(self, device: WindowsUSBDevice):
        info = device.to_dict()
        print(f"[SecureUSB] Device removed: {info['display_name']}")

        pending = self.pending.pop(device.device_id, None)
        if pending:
            timer = pending.get("timer")
            if isinstance(timer, QTimer):
                timer.stop()
            dialog = pending.get("dialog")
            if dialog:
                dialog.close()

        self.logger.log_event(
            EventAction.DEVICE_DISCONNECTED,
            vendor_id=info.get("vendor_id"),
            product_id=info.get("product_id"),
            product_name=info.get("display_name"),
            serial_number=info.get("serial_number"),
            device_path=info.get("instance_id"),
        )

    def _handle_timeout(self, device_id: str):
        pending = self.pending.get(device_id)
        if not pending:
            return

        device = pending["device"]
        print(f"[SecureUSB] Authorization timeout for {device.device_id}")
        self._deny_device(device, auto=True)

    def _authorize_device(self, device: WindowsUSBDevice, mode: str, code: str, remember: bool):
        if not self._verify_code(code):
            self.logger.log_event(
                EventAction.AUTH_FAILED,
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                serial_number=device.serial_number,
                details="Invalid TOTP or recovery code",
                success=False,
            )
            return False, "Authentication failed"

        if mode == AuthorizationMode.FULL_ACCESS.value or mode == "full":
            success = WindowsDeviceBlocker.allow_device(device.instance_id)
            event_type = EventAction.DEVICE_AUTHORIZED
        elif mode == AuthorizationMode.POWER_ONLY.value or mode == "power_only":
            success = WindowsDeviceBlocker.power_only(device.instance_id)
            event_type = EventAction.DEVICE_AUTHORIZED_POWER_ONLY
        else:
            success = False
            event_type = EventAction.DEVICE_DENIED

        if not success:
            return False, "Failed to update device state"

        self.logger.log_event(
            event_type,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            product_name=device.friendly_name,
            serial_number=device.serial_number,
            device_path=device.instance_id,
            auth_method="totp",
            success=True,
        )

        if remember and device.serial_number:
            self.whitelist.add_device(
                serial_number=device.serial_number,
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                vendor_name=device.friendly_name,
                product_name=device.friendly_name,
            )

        pending = self.pending.pop(device.device_id, None)
        if pending:
            timer = pending.get("timer")
            if isinstance(timer, QTimer):
                timer.stop()
            dialog = pending.get("dialog")
            if dialog:
                dialog.accept()

        return True, None

    def _deny_device(self, device: WindowsUSBDevice, auto: bool):
        WindowsDeviceBlocker.block_device(device.instance_id)
        info = device.to_dict()
        self.logger.log_event(
            EventAction.DEVICE_DENIED,
            vendor_id=info.get("vendor_id"),
            product_id=info.get("product_id"),
            serial_number=info.get("serial_number"),
            device_path=info.get("instance_id"),
            details="Authorization timeout" if auto else "User denied",
            success=not auto,
        )
        pending = self.pending.pop(device.device_id, None)
        if pending:
            timer = pending.get("timer")
            if isinstance(timer, QTimer):
                timer.stop()
            dialog = pending.get("dialog")
            if dialog:
                dialog.reject()

    def _verify_code(self, code: str) -> bool:
        if not code:
            return False

        if self.totp_auth and self.totp_auth.verify_code(code):
            return True

        for hashed in list(self.recovery_codes):
            if RecoveryCodeManager.verify_code(code, hashed):
                self.storage.remove_recovery_code(hashed)
                self.recovery_codes.remove(hashed)
                print(f"[SecureUSB] Recovery code used. Remaining: {len(self.recovery_codes)}")
                return True

        return False


def main():
    app = SecureUSBWindowsApp()
    app.start()


if __name__ == "__main__":
    main()
