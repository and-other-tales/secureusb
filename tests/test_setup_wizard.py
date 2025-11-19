#!/usr/bin/env python3
"""Logic-level tests for the GTK setup wizard using GI stubs."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import gi_stubs

gi_stubs.install()

from src.gui.setup_wizard import RecoveryCodeManager, SetupWizard


class TestSetupWizard(unittest.TestCase):
    def _wizard_stub(self):
        wizard = SetupWizard.__new__(SetupWizard)
        wizard.storage = MagicMock()
        wizard.authenticator = MagicMock()
        wizard.authenticator.get_secret.return_value = "SECRET"
        wizard.recovery_codes = ["CODE1", "CODE2"]
        wizard._clear_clipboard_after_timeout = MagicMock()
        return wizard

    def test_save_configuration_hashes_and_persists(self):
        wizard = self._wizard_stub()

        with patch.object(RecoveryCodeManager, "hash_code", side_effect=lambda code: f"HASH-{code}"):
            wizard._save_configuration()

        wizard.storage.save_auth_data.assert_called_once_with(
            "SECRET", ["HASH-CODE1", "HASH-CODE2"]
        )

    def test_on_copy_secret_pushes_to_clipboard(self):
        wizard = self._wizard_stub()
        clipboard = MagicMock()
        wizard.get_clipboard = MagicMock(return_value=clipboard)

        wizard._on_copy_secret(None)

        clipboard.set.assert_called_once_with("SECRET")
        wizard._clear_clipboard_after_timeout.assert_called_once()

    def test_clear_clipboard_timer_invokes_callback(self):
        wizard = SetupWizard.__new__(SetupWizard)
        clipboard = MagicMock()
        wizard.get_clipboard = MagicMock(return_value=clipboard)

        with patch("src.gui.setup_wizard.GLib.timeout_add_seconds") as mock_timer:
            wizard._clear_clipboard_after_timeout(15)

        mock_timer.assert_called_once()
        callback = mock_timer.call_args[0][1]
        self.assertFalse(callback())
        clipboard.set.assert_called_once_with("")


if __name__ == "__main__":
    unittest.main()
