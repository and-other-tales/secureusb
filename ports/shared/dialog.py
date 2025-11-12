#!/usr/bin/env python3
"""
Shared PySide6 authorization dialog used by the Windows and macOS ports.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


SubmitCallback = Callable[[str, str, bool], tuple[bool, Optional[str]]]
DenyCallback = Callable[[bool], None]


class AuthorizationDialog(QDialog):
    """
    Generic authorization dialog that prompts the user for a TOTP code.

    The dialog is platform-agnostic; platform-specific apps provide callbacks
    to handle submit/power-only/deny actions.
    """

    def __init__(self,
                 device_info: dict,
                 timeout_seconds: int,
                 on_submit: SubmitCallback,
                 on_power_only: SubmitCallback,
                 on_deny: DenyCallback,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("SecureUSB Authorization Required")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setModal(True)

        self.device_info = device_info
        self.remaining_seconds = timeout_seconds
        self.on_submit = on_submit
        self.on_power_only = on_power_only
        self.on_deny = on_deny
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._build_ui()
        self._update_countdown_label()
        self.timer.start(1000)

    def _build_ui(self):
        """Compose the dialog widgets."""
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("USB device connection detected")
        title.setProperty("class", "title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        device_label = QLabel(self._format_device_text())
        device_label.setWordWrap(True)
        layout.addWidget(device_label)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #d14343;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        otp_label = QLabel("Enter 6-digit TOTP code:")
        layout.addWidget(otp_label)

        self.otp_entry = QLineEdit()
        self.otp_entry.setMaxLength(6)
        self.otp_entry.setAlignment(Qt.AlignCenter)
        self.otp_entry.setPlaceholderText("000000")
        self.otp_entry.textChanged.connect(self._on_text_changed)
        self.otp_entry.returnPressed.connect(lambda: self._handle_submit("full"))
        layout.addWidget(self.otp_entry)

        self.countdown = QLabel()
        self.countdown.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown)

        self.remember_checkbox = QCheckBox("Remember this device (still requires TOTP)")
        if not self.device_info.get('serial_number'):
            self.remember_checkbox.setEnabled(False)
            self.remember_checkbox.setToolTip("Device has no serial number")
        layout.addWidget(self.remember_checkbox)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        deny_btn = QPushButton("Deny")
        deny_btn.clicked.connect(lambda: self._handle_deny(False))
        button_row.addWidget(deny_btn)

        power_btn = QPushButton("Power Only")
        power_btn.clicked.connect(lambda: self._handle_submit("power_only"))
        button_row.addWidget(power_btn)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setDefault(True)
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(lambda: self._handle_submit("full"))
        button_row.addWidget(self.connect_btn)

        layout.addLayout(button_row)
        self.setLayout(layout)

    def _format_device_text(self) -> str:
        name = self.device_info.get('display_name') or "Unknown device"
        vendor_id = self.device_info.get('vendor_id', '????')
        product_id = self.device_info.get('product_id', '????')
        serial = self.device_info.get('serial_number') or "N/A"
        return f"{name}\nVID:PID = {vendor_id}:{product_id}\nSerial: {serial}"

    def _on_text_changed(self, text: str):
        text = ''.join(ch for ch in text if ch.isdigit())
        if text != self.otp_entry.text():
            self.otp_entry.blockSignals(True)
            self.otp_entry.setText(text)
            self.otp_entry.blockSignals(False)

        self.connect_btn.setEnabled(len(text) == 6)

    def _update_countdown_label(self):
        self.countdown.setText(f"Time remaining: {self.remaining_seconds}s")
        if self.remaining_seconds <= 10:
            self.countdown.setStyleSheet("color: #d14343;")

    def _tick(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.countdown.setText("Authorization timed out")
            self._handle_deny(True)
            return

        self._update_countdown_label()

    def _handle_submit(self, mode: str):
        code = self.otp_entry.text().strip()
        if len(code) != 6:
            self.show_error("Enter a valid 6-digit code")
            return

        callback = self.on_submit if mode == "full" else self.on_power_only
        ok, error = callback(mode, code, self.remember_checkbox.isChecked())

        if not ok:
            self.show_error(error or "Authentication failed")
            self.otp_entry.selectAll()
            self.otp_entry.setFocus(Qt.TabFocusReason)
            return

        self.accept()

    def _handle_deny(self, auto: bool):
        self.on_deny(auto)
        self.reject()

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def closeEvent(self, event):
        if self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)
