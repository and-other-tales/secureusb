#!/usr/bin/env python3
"""
Polling-based USB monitor for Windows 11.

Uses PowerShell's Get-PnpDevice output to detect newly added/removed USB
devices without relying on WMI event subscriptions (which require elevated COM
initialisation inside a message loop).
"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Ensure repo modules are importable
from . import path_setup  # noqa: F401


POWERSHELL_ENUMERATION = r"""
$ErrorActionPreference = 'Stop'
Get-PnpDevice -Class USB |
    Where-Object { $_.InstanceId -like 'USB*' } |
    Select-Object InstanceId, FriendlyName, Status |
    ConvertTo-Json -Depth 3
"""


VID_PID_REGEX = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", re.IGNORECASE)


@dataclass
class WindowsUSBDevice:
    """Represents a USB device as reported by Windows."""

    instance_id: str
    friendly_name: str
    status: str
    vendor_id: str
    product_id: str
    serial_number: str

    @property
    def device_id(self) -> str:
        return self.instance_id

    def to_dict(self) -> Dict[str, str]:
        return {
            "device_id": self.device_id,
            "instance_id": self.instance_id,
            "display_name": self.friendly_name or "USB device",
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "serial_number": self.serial_number,
            "status": self.status,
        }


class WindowsUSBMonitor:
    """Polls Windows for USB device changes."""

    def __init__(self, poll_interval: float = 1.5):
        self.poll_interval = poll_interval
        self._events: "queue.Queue[Tuple[str, WindowsUSBDevice]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._known_devices: Dict[str, WindowsUSBDevice] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._running.set()
        self._thread = threading.Thread(target=self._run, name="WinUSBMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_events(self) -> List[Tuple[str, WindowsUSBDevice]]:
        """Return accumulated events since the last call."""
        events: List[Tuple[str, WindowsUSBDevice]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def _run(self):
        while self._running.is_set():
            current = self._enumerate_devices()

            # Added devices
            for device_id, device in current.items():
                if device_id not in self._known_devices:
                    self._events.put(("add", device))

            # Removed devices
            for device_id, device in list(self._known_devices.items()):
                if device_id not in current:
                    self._events.put(("remove", device))

            self._known_devices = current
            time.sleep(self.poll_interval)

    def _enumerate_devices(self) -> Dict[str, WindowsUSBDevice]:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", POWERSHELL_ENUMERATION],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return {}

        if result.returncode != 0 or not result.stdout.strip():
            return {}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

        # Convert single object to list if necessary
        if isinstance(data, dict):
            devices = [data]
        else:
            devices = data

        parsed: Dict[str, WindowsUSBDevice] = {}

        for entry in devices:
            instance_id = entry.get("InstanceId")
            if not instance_id:
                continue

            friendly = entry.get("FriendlyName") or "USB device"
            status = entry.get("Status") or "Unknown"
            vendor_id, product_id = self._extract_ids(instance_id)
            serial = self._extract_serial(instance_id)

            device = WindowsUSBDevice(
                instance_id=instance_id,
                friendly_name=friendly,
                status=status,
                vendor_id=vendor_id,
                product_id=product_id,
                serial_number=serial,
            )
            parsed[device.device_id] = device

        return parsed

    @staticmethod
    def _extract_ids(instance_id: str) -> Tuple[str, str]:
        match = VID_PID_REGEX.search(instance_id)
        if not match:
            return "", ""
        return match.group(1).lower(), match.group(2).lower()

    @staticmethod
    def _extract_serial(instance_id: str) -> str:
        if "\\" in instance_id:
            return instance_id.rsplit("\\", 1)[-1]
        return ""
