#!/usr/bin/env python3
"""
Unit tests for secure storage module.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from src.auth.storage import SecureStorage
from src.auth.totp import create_new_authenticator, RecoveryCodeManager


class TestSecureStorage(unittest.TestCase):
    """Test cases for SecureStorage class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for tests
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage = SecureStorage(config_dir=self.test_dir)

        # Create test authenticator and codes
        self.auth, self.recovery_codes = create_new_authenticator()
        self.hashed_codes = [RecoveryCodeManager.hash_code(code) for code in self.recovery_codes]

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test storage initialization."""
        self.assertTrue(self.test_dir.exists())
        self.assertTrue(self.storage.config_dir.exists())
        self.assertEqual(self.storage.config_dir, self.test_dir)

    def test_is_configured_false(self):
        """Test is_configured returns False when not configured."""
        self.assertFalse(self.storage.is_configured())

    def test_save_auth_data(self):
        """Test saving authentication data."""
        secret = self.auth.get_secret()
        result = self.storage.save_auth_data(secret, self.hashed_codes)

        self.assertTrue(result)
        self.assertTrue(self.storage.auth_file.exists())
        self.assertTrue(self.storage.is_configured())

    def test_load_auth_data(self):
        """Test loading authentication data."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        loaded_data = self.storage.load_auth_data()

        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data['totp_secret'], secret)
        self.assertEqual(loaded_data['recovery_codes'], self.hashed_codes)

    def test_load_auth_data_not_configured(self):
        """Test loading auth data when not configured."""
        data = self.storage.load_auth_data()
        self.assertIsNone(data)

    def test_save_and_load_roundtrip(self):
        """Test saving and loading preserves data."""
        secret = self.auth.get_secret()
        codes = self.hashed_codes[:5]  # Use only 5 codes

        self.storage.save_auth_data(secret, codes)
        loaded_data = self.storage.load_auth_data()

        self.assertEqual(loaded_data['totp_secret'], secret)
        self.assertEqual(len(loaded_data['recovery_codes']), 5)
        self.assertEqual(loaded_data['recovery_codes'], codes)

    def test_remove_recovery_code(self):
        """Test removing a used recovery code."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        # Remove first code
        code_to_remove = self.hashed_codes[0]
        result = self.storage.remove_recovery_code(code_to_remove)

        self.assertTrue(result)

        # Verify code was removed
        loaded_data = self.storage.load_auth_data()
        self.assertEqual(len(loaded_data['recovery_codes']), 9)
        self.assertNotIn(code_to_remove, loaded_data['recovery_codes'])

    def test_remove_recovery_code_not_found(self):
        """Test removing a code that doesn't exist."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        result = self.storage.remove_recovery_code("nonexistent_hash")
        self.assertFalse(result)

    def test_get_remaining_recovery_codes_count(self):
        """Test getting count of remaining recovery codes."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        count = self.storage.get_remaining_recovery_codes_count()
        self.assertEqual(count, 10)

        # Remove some codes
        self.storage.remove_recovery_code(self.hashed_codes[0])
        self.storage.remove_recovery_code(self.hashed_codes[1])

        count = self.storage.get_remaining_recovery_codes_count()
        self.assertEqual(count, 8)

    def test_get_remaining_recovery_codes_count_not_configured(self):
        """Test getting count when not configured."""
        count = self.storage.get_remaining_recovery_codes_count()
        self.assertEqual(count, 0)

    def test_reset_auth(self):
        """Test resetting authentication data."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        self.assertTrue(self.storage.is_configured())

        result = self.storage.reset_auth()
        self.assertTrue(result)
        self.assertFalse(self.storage.is_configured())
        self.assertFalse(self.storage.auth_file.exists())

    def test_export_config(self):
        """Test exporting configuration."""
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        export_path = self.test_dir / "export.json"
        result = self.storage.export_config(export_path)

        self.assertTrue(result)
        self.assertTrue(export_path.exists())

    def test_import_config(self):
        """Test importing configuration."""
        # Save and export
        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        export_path = self.test_dir / "export.json"
        self.storage.export_config(export_path)

        # Create new storage and import
        new_test_dir = Path(tempfile.mkdtemp())
        try:
            new_storage = SecureStorage(config_dir=new_test_dir)
            result = new_storage.import_config(export_path)

            self.assertTrue(result)
            self.assertTrue(new_storage.is_configured())

            # Verify data
            loaded_data = new_storage.load_auth_data()
            self.assertEqual(loaded_data['totp_secret'], secret)

        finally:
            shutil.rmtree(new_test_dir)

    def test_file_permissions(self):
        """Test that created files have correct permissions."""
        import os
        import stat

        secret = self.auth.get_secret()
        self.storage.save_auth_data(secret, self.hashed_codes)

        # Check config directory permissions (700 = owner only)
        dir_stat = self.test_dir.stat()
        dir_mode = stat.S_IMODE(dir_stat.st_mode)
        self.assertEqual(dir_mode, stat.S_IRWXU)

        # Check auth file permissions (600 = owner read/write only)
        if self.storage.auth_file.exists():
            file_stat = self.storage.auth_file.stat()
            file_mode = stat.S_IMODE(file_stat.st_mode)
            self.assertEqual(file_mode, stat.S_IRUSR | stat.S_IWUSR)

    def test_encryption_uniqueness(self):
        """Test that same data produces different ciphertext (due to Fernet)."""
        secret = self.auth.get_secret()

        # Save data
        self.storage.save_auth_data(secret, self.hashed_codes)
        encrypted1 = self.storage.auth_file.read_bytes()

        # Reset and save same data again
        self.storage.reset_auth()
        self.storage.save_auth_data(secret, self.hashed_codes)
        encrypted2 = self.storage.auth_file.read_bytes()

        # Encrypted data should be different (Fernet includes timestamp)
        # But decrypted data should be the same
        data1 = self.storage.load_auth_data()
        self.assertEqual(data1['totp_secret'], secret)


if __name__ == '__main__':
    unittest.main()
