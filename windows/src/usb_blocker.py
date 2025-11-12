#!/usr/bin/env python3
"""
Windows-specific helpers to disable/enable USB devices using pnputil.
"""

from __future__ import annotations

import subprocess
from typing import Tuple

# Ensure repo modules available
from . import path_setup  # noqa: F401


class WindowsDeviceBlocker:
    """Wrapper around pnputil.exe for enabling/disabling USB devices."""

    @staticmethod
    def block_device(instance_id: str) -> bool:
        """
        Disable the specified USB device.

        Requires administrative privileges.
        """
        return WindowsDeviceBlocker._run_pnputil("/disable-device", instance_id)

    @staticmethod
    def allow_device(instance_id: str) -> bool:
        """Re-enable the specified USB device."""
        return WindowsDeviceBlocker._run_pnputil("/enable-device", instance_id)

    @staticmethod
    def power_only(instance_id: str) -> bool:
        """
        Power-only mode is approximated by keeping the device disabled.

        Most hardware will continue to deliver power even if the USB interface
        is disabled in Windows. This mirrors the Linux behaviour where power-only
        is implemented via kernel-level block.
        """
        return WindowsDeviceBlocker.block_device(instance_id)

    @staticmethod
    def _run_pnputil(*args: str) -> bool:
        cmd = ["pnputil.exe"] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            print("Error: pnputil.exe not found (requires Windows 10/11).")
            return False

        if result.returncode != 0:
            print(f"[pnputil] Command failed: {' '.join(cmd)}")
            print(result.stdout.strip())
            print(result.stderr.strip())
            return False

        return True
