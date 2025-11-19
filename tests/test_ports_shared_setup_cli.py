#!/usr/bin/env python3
"""
Unit tests for ports/shared/setup_cli.py

Verifies the cross-platform CLI wizard handles provisioning correctly and
persists secrets through the SecureStorage abstraction.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ports.shared import setup_cli  # noqa: E402
from src.auth import RecoveryCodeManager  # noqa: E402


class DummyStorage:
    """Simple stand-in for SecureStorage."""

    def __init__(self, configured: bool):
        self._configured = configured
        self.saved_payload = None
        self.config_dir = Path("/tmp/secureusb-test")

    def is_configured(self) -> bool:
        return self._configured

    def save_auth_data(self, secret: str, hashed_codes: List[str]) -> bool:
        self.saved_payload = SimpleNamespace(secret=secret, hashed=hashed_codes)
        return True


class DummyQRCode:
    """Minimal stub for qrcode.QRCode used by the CLI."""

    def __init__(self, border: int = 1):
        self.border = border
        self.data = None

    def add_data(self, data: str):
        self.data = data

    def make(self, fit: bool = True):
        return True

    def print_ascii(self, invert: bool = True):
        return "QR"


class DummyAuthenticator:
    """Collects provisioning URI calls for verification."""

    def __init__(self):
        self._secret = "ABCDEFGHIJKLMNOP"
        self.uri_calls = []

    def get_secret(self) -> str:
        return self._secret

    def get_provisioning_uri(self, name: str = "SecureUSB", issuer: Optional[str] = None) -> str:
        self.uri_calls.append((name, issuer))
        return f"uri://{name}/{issuer or 'host'}"

    def verify_code(self, code: str) -> bool:
        return code == "123456"


class TestRunCliSetup(unittest.TestCase):
    """Tests for run_cli_setup helper."""

    def test_returns_early_when_already_configured(self):
        """Existing installs should not attempt to regenerate secrets."""
        storage = DummyStorage(configured=True)

        with patch.object(setup_cli, "SecureStorage", return_value=storage), \
             patch.object(setup_cli, "create_new_authenticator") as mock_create:
            exit_code = setup_cli.run_cli_setup("Windows")

        self.assertEqual(exit_code, 0)
        mock_create.assert_not_called()
        self.assertIsNone(storage.saved_payload)

    def test_provisions_and_saves_credentials(self):
        """Happy-path provisioning stores hashed recovery codes."""
        storage = DummyStorage(configured=False)
        authenticator = DummyAuthenticator()
        recovery_codes = ["ABCD-EFGH-IJKL"]

        with patch.object(setup_cli, "SecureStorage", return_value=storage), \
             patch.object(setup_cli, "create_new_authenticator", return_value=(authenticator, recovery_codes)), \
             patch.object(setup_cli.qrcode, "QRCode", DummyQRCode), \
             patch.object(setup_cli, "input", lambda prompt='': "123456"):
            exit_code = setup_cli.run_cli_setup("Desktop")

        self.assertEqual(exit_code, 0)
        self.assertEqual(authenticator.uri_calls, [("SecureUSB", "SecureUSB")])

        expected_hash = RecoveryCodeManager.hash_code(recovery_codes[0])
        self.assertIsNotNone(storage.saved_payload)
        self.assertEqual(storage.saved_payload.secret, authenticator.get_secret())
        self.assertEqual(storage.saved_payload.hashed, [expected_hash])


if __name__ == '__main__':
    unittest.main()
