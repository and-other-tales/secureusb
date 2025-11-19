#!/usr/bin/env python3
"""
Path utilities for SecureUSB.

Provides a single place to resolve where configuration, logs, and
other writable assets should live. This allows the root daemon and
user-space tools to agree on the same directory even though they run
with different $HOME values.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Optional


ENV_VAR_NAME = "SECUREUSB_CONFIG_DIR"


def _default_system_dir() -> Path:
    """Return the OS-specific system directory for SecureUSB data."""
    system = platform.system().lower()

    if system == "windows":
        base = os.environ.get("PROGRAMDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "SecureUSB"

    if system == "darwin":
        return Path("/Library/Application Support/SecureUSB")

    # Linux / other Unix
    return Path("/var/lib/secureusb")


def _default_pointer_file(system_dir: Path) -> Path:
    """Return the pointer file path that stores the active config dir."""
    system = platform.system().lower()

    if system == "windows":
        return system_dir / "config_dir.txt"

    if system == "darwin":
        return system_dir / "config_dir"

    return Path("/etc/secureusb/config_dir")


SYSTEM_CONFIG_DIR = _default_system_dir()
POINTER_FILE = _default_pointer_file(SYSTEM_CONFIG_DIR)


def _read_pointer_file() -> Optional[Path]:
    """
    Try to read a config directory hint from POINTER_FILE.

    Returns:
        Path if file exists and contains a non-empty path string.
    """
    try:
        if POINTER_FILE.exists():
            content = POINTER_FILE.read_text().strip()
            if content:
                return Path(content).expanduser()
    except Exception:
        pass

    return None


def _is_writable_path(path: Path) -> bool:
    """Return True if the current user can create/read files under path."""
    try:
        candidate = path
        if not candidate.exists():
            # Walk up until we find an existing parent to test permissions on.
            candidate = candidate.parent
            while candidate and not candidate.exists():
                next_parent = candidate.parent
                if next_parent == candidate:
                    break
                candidate = next_parent
        return os.access(candidate, os.W_OK | os.X_OK)
    except Exception:
        return False


def resolve_config_dir(explicit_dir: Optional[Path] = None) -> Path:
    """
    Determine which directory SecureUSB should use for config/logging.

    Resolution order:
        1. Caller-provided path
        2. SECUREUSB_CONFIG_DIR environment variable
        3. Pointer file (/etc/secureusb/config_dir)
        4. System directory (/var/lib/secureusb) if it exists
        5. User default (~/.config/secureusb)

    Args:
        explicit_dir: Optional override provided by callers/tests.

    Returns:
        Path to the directory to use (directory may not exist yet).
    """
    if explicit_dir:
        return Path(explicit_dir).expanduser()

    env_path = os.environ.get(ENV_VAR_NAME)
    if env_path:
        return Path(env_path).expanduser()

    pointer_path = _read_pointer_file()
    if pointer_path and _is_writable_path(pointer_path):
        return pointer_path

    if SYSTEM_CONFIG_DIR.exists() and _is_writable_path(SYSTEM_CONFIG_DIR):
        return SYSTEM_CONFIG_DIR

    return Path.home() / ".config" / "secureusb"
