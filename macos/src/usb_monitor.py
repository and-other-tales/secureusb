#!/usr/bin/env python3
"""
Polling USB monitor for macOS 12+ using system_profiler JSON output.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from . import path_setup  # noqa: F401


SYSTEM_PROFILER_CMD = ["system_profiler", "SPUSBDataType", "-json"]


@dataclass
class MacUSBDevice:
    """Represents a macOS USB device."""

    device_id: str
    display_name: str
    vendor_id: str
    product_id: str
    serial_number: str
    location_id: str
    bsd_name: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        return {
            "device_id": self.device_id,
            "display_name": self.display_name or "USB device",
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "serial_number": self.serial_number,
            "location_id": self.location_id,
            "bsd_name": self.bsd_name or "",
        }


class MacUSBMonitor:
    """Polls macOS for USB device changes."""

    def __init__(self, poll_interval: float = 2.5):
        self.poll_interval = poll_interval
        self._events: "queue.Queue[Tuple[str, MacUSBDevice]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._known_devices: Dict[str, MacUSBDevice] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="MacUSBMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_events(self) -> List[Tuple[str, MacUSBDevice]]:
        events: List[Tuple[str, MacUSBDevice]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def _run(self):
        while self._running.is_set():
            current = self._enumerate_devices()
            for device_id, device in current.items():
                if device_id not in self._known_devices:
                    self._events.put(("add", device))

            for device_id, device in list(self._known_devices.items()):
                if device_id not in current:
                    self._events.put(("remove", device))

            self._known_devices = current
            time.sleep(self.poll_interval)

    def _enumerate_devices(self) -> Dict[str, MacUSBDevice]:
        try:
            result = subprocess.run(
                SYSTEM_PROFILER_CMD,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return {}

        if result.returncode != 0 or not result.stdout:
            return {}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

        devices: Dict[str, MacUSBDevice] = {}
        for entry in data.get("SPUSBDataType", []):
            for device_entry in self._flatten_items(entry.get("_items", [])):
                device = self._parse_device(device_entry)
                if device:
                    devices[device.device_id] = device

        return devices

    def _flatten_items(self, items: Iterable[dict]) -> Iterable[dict]:
        for item in items:
            children = item.get("_items", [])
            if "vendor_id" in item and "product_id" in item:
                yield item
            if children:
                yield from self._flatten_items(children)

    def _parse_device(self, entry: dict) -> Optional[MacUSBDevice]:
        location = entry.get("location_id") or ""
        if not location:
            return None

        location_clean = location.split("/")[0].strip()
        device_id = location_clean or entry.get("serial_num") or entry.get("_name")

        vendor_id = self._extract_hex(entry.get("vendor_id", ""))
        product_id = self._extract_hex(entry.get("product_id", ""))

        return MacUSBDevice(
            device_id=device_id,
            display_name=entry.get("_name", "USB device"),
            vendor_id=vendor_id,
            product_id=product_id,
            serial_number=entry.get("serial_num", ""),
            location_id=location_clean,
            bsd_name=entry.get("bsd_name"),
        )

    @staticmethod
    def _extract_hex(field: str) -> str:
        if not field:
            return ""
        token = field.split()[0]
        return token.replace("0x", "").lower()
