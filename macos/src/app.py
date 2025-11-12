#!/usr/bin/env python3
"""
SecureUSB macOS port targeting Monterey and newer.

Implements the same user-facing behaviour as the Linux daemon using PySide6 for
the authorization dialog and IOKit/diskutil hooks for blocking devices.
"""

from __future__ import annotations

import signal
import sys
from typing import Dict, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from . import path_setup  # noqa: F401
from .usb_blocker import MacDeviceBlocker
from .usb_monitor import MacUSBDevice, MacUSBMonitor
from ports.shared import AuthorizationDialog
from src.auth import RecoveryCodeManager, SecureStorage, TOTPAuthenticator
from src.utils import Config, DeviceWhitelist, EventAction, USBLogger


class SecureUSBMacApp(QApplication):
    """Main macOS GUI/background agent."""

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
            print("SecureUSB is not configured. Run macos/src/setup_cli.py first.")
            sys.exit(1)

        self.monitor = MacUSBMonitor()
        self.event_poller = QTimer()
        self.event_poller.setInterval(600)
        self.event_poller.timeout.connect(self._drain_events)

        self.pending: Dict[str, Dict] = {}

        self.aboutToQuit.connect(self._cleanup)
        signal.signal(signal.SIGINT, lambda *_: self.quit())

    def start(self):
        self.monitor.start()
        self.event_poller.start()
        print("SecureUSB macOS client running. Press Ctrl+C to exit.")
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

    def _handle_device_connected(self, device: MacUSBDevice):
        info = device.to_dict()
        print(f"[SecureUSB] Device connected: {info['display_name']}")

        self.logger.log_event(
            EventAction.DEVICE_CONNECTED,
            vendor_id=info.get("vendor_id"),
            product_id=info.get("product_id"),
            product_name=info.get("display_name"),
            serial_number=info.get("serial_number"),
            device_path=info.get("location_id"),
        )

        if not self.config.is_enabled():
            print("[SecureUSB] Protection disabled, skipping authorization.")
            return

        if not self.totp_auth:
            print("[SecureUSB] TOTP not configured.")
            return

        MacDeviceBlocker.block_device(device.location_id, device.bsd_name)

        timeout_seconds = self.config.get_timeout()
        dialog = AuthorizationDialog(
            device_info=info,
            timeout_seconds=timeout_seconds,
            on_submit=lambda mode, code, remember: self._authorize_device(device, mode, code, remember),
            on_power_only=lambda mode, code, remember: self._power_only(device, mode, code, remember),
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

    def _handle_device_removed(self, device: MacUSBDevice):
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
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            product_name=device.display_name,
            serial_number=device.serial_number,
            device_path=device.location_id,
        )

    def _handle_timeout(self, device_id: str):
        pending = self.pending.get(device_id)
        if not pending:
            return
        device = pending["device"]
        print(f"[SecureUSB] Authorization timeout for {device.display_name}")
        self._deny_device(device, auto=True)

    def _authorize_device(self, device: MacUSBDevice, mode: str, code: str, remember: bool):
        if not self._verify_code(code):
            self.logger.log_event(
                EventAction.AUTH_FAILED,
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                serial_number=device.serial_number,
                success=False,
                details="Invalid TOTP or recovery code",
            )
            return False, "Authentication failed"

        success = MacDeviceBlocker.allow_device(device.location_id)
        if not success:
            return False, "Failed to enable device"

        self.logger.log_event(
            EventAction.DEVICE_AUTHORIZED,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            product_name=device.display_name,
            serial_number=device.serial_number,
            device_path=device.location_id,
            auth_method="totp",
            success=True,
        )

        if remember and device.serial_number:
            self.whitelist.add_device(
                serial_number=device.serial_number,
                vendor_id=device.vendor_id,
                product_id=device.product_id,
                vendor_name=device.display_name,
                product_name=device.display_name,
            )

        self._close_dialog(device.device_id, accept=True)
        return True, None

    def _power_only(self, device: MacUSBDevice, mode: str, code: str, remember: bool):
        if not self._verify_code(code):
            return False, "Authentication failed"

        success = MacDeviceBlocker.power_only(device.location_id)
        if not success:
            return False, "Failed to keep device blocked"

        self.logger.log_event(
            EventAction.DEVICE_AUTHORIZED_POWER_ONLY,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            product_name=device.display_name,
            serial_number=device.serial_number,
            device_path=device.location_id,
            auth_method="totp",
            success=True,
        )

        self._close_dialog(device.device_id, accept=True)
        return True, None

    def _deny_device(self, device: MacUSBDevice, auto: bool):
        MacDeviceBlocker.block_device(device.location_id, device.bsd_name)
        self.logger.log_event(
            EventAction.DEVICE_DENIED,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            serial_number=device.serial_number,
            device_path=device.location_id,
            details="Authorization timeout" if auto else "User denied",
            success=not auto,
        )
        self._close_dialog(device.device_id, accept=False)

    def _close_dialog(self, device_id: str, accept: bool):
        pending = self.pending.pop(device_id, None)
        if not pending:
            return
        timer = pending.get("timer")
        if isinstance(timer, QTimer):
            timer.stop()
        dialog = pending.get("dialog")
        if dialog:
            if accept:
                dialog.accept()
            else:
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
    app = SecureUSBMacApp()
    app.start()


if __name__ == "__main__":
    main()
