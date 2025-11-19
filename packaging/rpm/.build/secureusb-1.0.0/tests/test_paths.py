#!/usr/bin/env python3
"""
Unit tests for src/utils/paths.py

Tests path resolution logic for configuration directory discovery.
"""

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.paths import (
    resolve_config_dir,
    _default_system_dir,
    _default_pointer_file,
    _read_pointer_file,
    ENV_VAR_NAME,
    SYSTEM_CONFIG_DIR,
    POINTER_FILE
)


class TestPathsDefaultSystemDir(unittest.TestCase):
    """Test _default_system_dir function."""

    @patch('platform.system')
    def test_default_system_dir_linux(self, mock_system):
        """Test default system directory on Linux."""
        mock_system.return_value = 'Linux'
        result = _default_system_dir()
        self.assertEqual(result, Path("/var/lib/secureusb"))

    @patch('platform.system')
    def test_default_system_dir_darwin(self, mock_system):
        """Test default system directory on macOS."""
        mock_system.return_value = 'Darwin'
        result = _default_system_dir()
        self.assertEqual(result, Path("/Library/Application Support/SecureUSB"))

    @patch('platform.system')
    @patch.dict(os.environ, {'PROGRAMDATA': 'C:\\ProgramData'})
    def test_default_system_dir_windows_with_programdata(self, mock_system):
        """Test default system directory on Windows with PROGRAMDATA."""
        mock_system.return_value = 'Windows'
        result = _default_system_dir()
        self.assertEqual(result, Path("C:\\ProgramData") / "SecureUSB")

    @patch('platform.system')
    @patch.dict(os.environ, {}, clear=True)
    @patch('pathlib.Path.home')
    def test_default_system_dir_windows_without_programdata(self, mock_home, mock_system):
        """Test default system directory on Windows without PROGRAMDATA."""
        mock_system.return_value = 'Windows'
        mock_home.return_value = Path("C:\\Users\\TestUser")
        result = _default_system_dir()
        self.assertEqual(result, Path("C:\\Users\\TestUser") / "AppData" / "Local" / "SecureUSB")


class TestPathsDefaultPointerFile(unittest.TestCase):
    """Test _default_pointer_file function."""

    @patch('platform.system')
    def test_default_pointer_file_linux(self, mock_system):
        """Test pointer file path on Linux."""
        mock_system.return_value = 'Linux'
        system_dir = Path("/var/lib/secureusb")
        result = _default_pointer_file(system_dir)
        self.assertEqual(result, Path("/etc/secureusb/config_dir"))

    @patch('platform.system')
    def test_default_pointer_file_darwin(self, mock_system):
        """Test pointer file path on macOS."""
        mock_system.return_value = 'Darwin'
        system_dir = Path("/Library/Application Support/SecureUSB")
        result = _default_pointer_file(system_dir)
        self.assertEqual(result, system_dir / "config_dir")

    @patch('platform.system')
    def test_default_pointer_file_windows(self, mock_system):
        """Test pointer file path on Windows."""
        mock_system.return_value = 'Windows'
        system_dir = Path("C:\\ProgramData\\SecureUSB")
        result = _default_pointer_file(system_dir)
        self.assertEqual(result, system_dir / "config_dir.txt")


class TestPathsReadPointerFile(unittest.TestCase):
    """Test _read_pointer_file function."""

    def test_read_pointer_file_exists(self):
        """Test reading pointer file when it exists."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_path = "/tmp/test_config"
            f.write(test_path)
            temp_file = Path(f.name)

        try:
            with patch('src.utils.paths.POINTER_FILE', temp_file):
                result = _read_pointer_file()
                self.assertEqual(result, Path(test_path))
        finally:
            temp_file.unlink()

    def test_read_pointer_file_not_exists(self):
        """Test reading pointer file when it doesn't exist."""
        fake_path = Path("/nonexistent/pointer/file")
        with patch('src.utils.paths.POINTER_FILE', fake_path):
            result = _read_pointer_file()
            self.assertIsNone(result)

    def test_read_pointer_file_empty(self):
        """Test reading empty pointer file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("")
            temp_file = Path(f.name)

        try:
            with patch('src.utils.paths.POINTER_FILE', temp_file):
                result = _read_pointer_file()
                self.assertIsNone(result)
        finally:
            temp_file.unlink()

    def test_read_pointer_file_with_tilde(self):
        """Test pointer file with tilde expansion."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("~/.config/secureusb")
            temp_file = Path(f.name)

        try:
            with patch('src.utils.paths.POINTER_FILE', temp_file):
                result = _read_pointer_file()
                self.assertIsNotNone(result)
                self.assertNotIn('~', str(result))  # Tilde should be expanded
        finally:
            temp_file.unlink()


class TestPathsResolveConfigDir(unittest.TestCase):
    """Test resolve_config_dir function."""

    def test_resolve_explicit_dir(self):
        """Test resolution with explicit directory provided."""
        explicit_path = Path("/tmp/test_explicit")
        result = resolve_config_dir(explicit_path)
        self.assertEqual(result, explicit_path)

    def test_resolve_explicit_dir_with_tilde(self):
        """Test resolution with explicit directory containing tilde."""
        result = resolve_config_dir(Path("~/test_config"))
        self.assertNotIn('~', str(result))

    @patch.dict(os.environ, {ENV_VAR_NAME: '/tmp/env_config'})
    def test_resolve_from_environment(self):
        """Test resolution from environment variable."""
        result = resolve_config_dir()
        self.assertEqual(result, Path("/tmp/env_config"))

    @patch.dict(os.environ, {ENV_VAR_NAME: '~/env_config'})
    def test_resolve_from_environment_with_tilde(self):
        """Test resolution from environment variable with tilde."""
        result = resolve_config_dir()
        self.assertNotIn('~', str(result))

    def test_resolve_from_pointer_file(self):
        """Test resolution from pointer file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_path = "/tmp/pointer_config"
            f.write(test_path)
            temp_file = Path(f.name)

        try:
            with patch('src.utils.paths.POINTER_FILE', temp_file):
                with patch.dict(os.environ, {}, clear=True):  # No env var
                    result = resolve_config_dir()
                    self.assertEqual(result, Path(test_path))
        finally:
            temp_file.unlink()

    def test_resolve_from_system_dir_if_exists(self):
        """Test resolution from system directory if it exists."""
        with tempfile.TemporaryDirectory() as temp_system_dir:
            system_path = Path(temp_system_dir)
            with patch('src.utils.paths.SYSTEM_CONFIG_DIR', system_path):
                with patch('src.utils.paths.POINTER_FILE', Path("/nonexistent")):
                    with patch.dict(os.environ, {}, clear=True):
                        result = resolve_config_dir()
                        self.assertEqual(result, system_path)

    def test_resolve_fallback_to_user_default(self):
        """Test fallback to user default when nothing else exists."""
        # Create a temporary path that exists() can check without permission errors
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_system = Path(temp_dir) / "nonexistent_system"
            nonexistent_pointer = Path(temp_dir) / "nonexistent_pointer"

            with patch('src.utils.paths.SYSTEM_CONFIG_DIR', nonexistent_system):
                with patch('src.utils.paths.POINTER_FILE', nonexistent_pointer):
                    with patch.dict(os.environ, {}, clear=True):
                        result = resolve_config_dir()
                        expected = Path.home() / ".config" / "secureusb"
                        self.assertEqual(result, expected)

    def test_resolve_priority_order(self):
        """Test that resolution follows correct priority order."""
        # Priority 1: Explicit dir
        explicit = Path("/tmp/explicit")
        result = resolve_config_dir(explicit)
        self.assertEqual(result, explicit)

        # Priority 2: Environment variable (when no explicit dir)
        with patch.dict(os.environ, {ENV_VAR_NAME: '/tmp/env'}):
            result = resolve_config_dir()
            self.assertEqual(result, Path("/tmp/env"))


class TestPathsEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_resolve_config_dir_with_none(self):
        """Test that None is handled correctly."""
        # Should not raise error, should use resolution logic
        result = resolve_config_dir(None)
        self.assertIsInstance(result, Path)

    def test_resolve_config_dir_with_empty_string(self):
        """Test that empty string is handled correctly."""
        result = resolve_config_dir(Path(""))
        self.assertIsInstance(result, Path)

    def test_pointer_file_read_error(self):
        """Test handling of read errors in pointer file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_file = Path(f.name)

        try:
            # Make file unreadable
            os.chmod(temp_file, 0o000)
            with patch('src.utils.paths.POINTER_FILE', temp_file):
                result = _read_pointer_file()
                # Should return None on error, not raise exception
                self.assertIsNone(result)
        finally:
            os.chmod(temp_file, 0o644)  # Restore permissions
            temp_file.unlink()

    def test_path_expansion_consistency(self):
        """Test that tilde expansion is consistent."""
        test_path = "~/test"
        result1 = resolve_config_dir(Path(test_path))
        result2 = resolve_config_dir(Path(test_path))
        self.assertEqual(result1, result2)


class TestPathsIntegration(unittest.TestCase):
    """Integration tests for path resolution."""

    def test_multiple_resolution_calls_consistent(self):
        """Test that multiple calls return consistent results."""
        result1 = resolve_config_dir()
        result2 = resolve_config_dir()
        self.assertEqual(result1, result2)

    def test_system_constants_valid(self):
        """Test that system constants are valid paths."""
        self.assertIsInstance(SYSTEM_CONFIG_DIR, Path)
        self.assertIsInstance(POINTER_FILE, Path)

    def test_env_var_name_is_string(self):
        """Test that environment variable name is a string."""
        self.assertIsInstance(ENV_VAR_NAME, str)
        self.assertEqual(ENV_VAR_NAME, "SECUREUSB_CONFIG_DIR")


if __name__ == '__main__':
    unittest.main()
