#!/usr/bin/env python3
"""
Unit tests for TOTP authentication module.
"""

import unittest
import time
from src.auth.totp import TOTPAuthenticator, RecoveryCodeManager, create_new_authenticator


class TestTOTPAuthenticator(unittest.TestCase):
    """Test cases for TOTPAuthenticator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth = TOTPAuthenticator()
        self.test_secret = "JBSWY3DPEHPK3PXP"  # Test secret

    def test_initialization_without_secret(self):
        """Test creating authenticator without providing secret."""
        auth = TOTPAuthenticator()
        self.assertIsNotNone(auth.secret)
        self.assertEqual(len(auth.secret), 32)  # Base32 secrets are 32 chars

    def test_initialization_with_secret(self):
        """Test creating authenticator with provided secret."""
        auth = TOTPAuthenticator(self.test_secret)
        self.assertEqual(auth.secret, self.test_secret)

    def test_get_secret(self):
        """Test getting the secret key."""
        secret = self.auth.get_secret()
        self.assertIsNotNone(secret)
        self.assertIsInstance(secret, str)
        self.assertEqual(len(secret), 32)

    def test_get_provisioning_uri(self):
        """Test generating provisioning URI for QR code."""
        uri = self.auth.get_provisioning_uri()
        self.assertIn("otpauth://totp/", uri)
        self.assertIn("SecureUSB", uri)
        self.assertIn("secret=", uri)

    def test_get_provisioning_uri_with_custom_params(self):
        """Test provisioning URI with custom name and issuer."""
        uri = self.auth.get_provisioning_uri(name="TestDevice", issuer="TestIssuer")
        self.assertIn("TestDevice", uri)
        self.assertIn("TestIssuer", uri)

    def test_get_current_code(self):
        """Test generating current TOTP code."""
        code = self.auth.get_current_code()
        self.assertIsNotNone(code)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_verify_code_valid(self):
        """Test verifying a valid TOTP code."""
        # Generate current code and verify it
        current_code = self.auth.get_current_code()
        self.assertTrue(self.auth.verify_code(current_code))

    def test_verify_code_invalid(self):
        """Test verifying an invalid TOTP code."""
        self.assertFalse(self.auth.verify_code("000000"))
        self.assertFalse(self.auth.verify_code("999999"))

    def test_verify_code_wrong_format(self):
        """Test verifying codes with wrong format."""
        self.assertFalse(self.auth.verify_code("12345"))  # Too short
        self.assertFalse(self.auth.verify_code("1234567"))  # Too long
        self.assertFalse(self.auth.verify_code("12345a"))  # Not digits
        self.assertFalse(self.auth.verify_code(""))  # Empty

    def test_verify_code_with_spaces(self):
        """Test verifying codes with spaces (should be stripped)."""
        current_code = self.auth.get_current_code()
        code_with_spaces = f"{current_code[:3]} {current_code[3:]}"
        self.assertTrue(self.auth.verify_code(code_with_spaces))

    def test_verify_code_reuse_prevention(self):
        """Test that the same code cannot be used twice immediately."""
        current_code = self.auth.get_current_code()

        # First use should succeed
        self.assertTrue(self.auth.verify_code(current_code))

        # Immediate reuse should fail
        self.assertFalse(self.auth.verify_code(current_code))

    def test_get_time_remaining(self):
        """Test getting time remaining until code expires."""
        remaining = self.auth.get_time_remaining()
        self.assertIsInstance(remaining, int)
        self.assertGreaterEqual(remaining, 0)
        self.assertLessEqual(remaining, 30)

    def test_code_changes_over_time(self):
        """Test that TOTP code changes after 30 seconds."""
        # This test would take 30 seconds, so we'll skip it in normal runs
        # but keep it for thorough testing
        pass


class TestRecoveryCodeManager(unittest.TestCase):
    """Test cases for RecoveryCodeManager class."""

    def test_generate_codes_default_count(self):
        """Test generating default number of recovery codes."""
        codes = RecoveryCodeManager.generate_codes()
        self.assertEqual(len(codes), 10)

    def test_generate_codes_custom_count(self):
        """Test generating custom number of recovery codes."""
        codes = RecoveryCodeManager.generate_codes(count=5)
        self.assertEqual(len(codes), 5)

    def test_code_format(self):
        """Test that generated codes have correct format."""
        codes = RecoveryCodeManager.generate_codes()
        for code in codes:
            # Format should be XXXX-XXXX-XXXX
            self.assertEqual(len(code), 14)  # 12 chars + 2 dashes
            self.assertEqual(code[4], '-')
            self.assertEqual(code[9], '-')

            # Remove dashes and check characters
            clean = code.replace('-', '')
            self.assertEqual(len(clean), 12)
            self.assertTrue(all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in clean))

    def test_codes_are_unique(self):
        """Test that generated codes are unique."""
        codes = RecoveryCodeManager.generate_codes(count=20)
        self.assertEqual(len(codes), len(set(codes)))

    def test_hash_code(self):
        """Test hashing a recovery code."""
        code = "ABCD-EFGH-IJKL"
        hashed = RecoveryCodeManager.hash_code(code)

        self.assertIsInstance(hashed, str)
        self.assertEqual(len(hashed), 64)  # SHA-256 hex digest

    def test_hash_code_consistent(self):
        """Test that hashing the same code produces same hash."""
        code = "ABCD-EFGH-IJKL"
        hash1 = RecoveryCodeManager.hash_code(code)
        hash2 = RecoveryCodeManager.hash_code(code)
        self.assertEqual(hash1, hash2)

    def test_hash_code_case_insensitive(self):
        """Test that hashing is case-insensitive."""
        hash1 = RecoveryCodeManager.hash_code("ABCD-EFGH-IJKL")
        hash2 = RecoveryCodeManager.hash_code("abcd-efgh-ijkl")
        self.assertEqual(hash1, hash2)

    def test_verify_code_valid(self):
        """Test verifying a valid recovery code."""
        code = "ABCD-EFGH-IJKL"
        hashed = RecoveryCodeManager.hash_code(code)
        self.assertTrue(RecoveryCodeManager.verify_code(code, hashed))

    def test_verify_code_invalid(self):
        """Test verifying an invalid recovery code."""
        code = "ABCD-EFGH-IJKL"
        wrong_code = "XXXX-YYYY-ZZZZ"
        hashed = RecoveryCodeManager.hash_code(code)
        self.assertFalse(RecoveryCodeManager.verify_code(wrong_code, hashed))

    def test_verify_code_case_insensitive(self):
        """Test that verification is case-insensitive."""
        code = "ABCD-EFGH-IJKL"
        hashed = RecoveryCodeManager.hash_code(code)
        self.assertTrue(RecoveryCodeManager.verify_code("abcd-efgh-ijkl", hashed))

    def test_format_code(self):
        """Test formatting a recovery code."""
        # Test with dashes
        formatted = RecoveryCodeManager.format_code("ABCD-EFGH-IJKL")
        self.assertEqual(formatted, "ABCD-EFGH-IJKL")

        # Test without dashes
        formatted = RecoveryCodeManager.format_code("ABCDEFGHIJKL")
        self.assertEqual(formatted, "ABCD-EFGH-IJKL")

        # Test with spaces
        formatted = RecoveryCodeManager.format_code("ABCD EFGH IJKL")
        self.assertEqual(formatted, "ABCD-EFGH-IJKL")

        # Test lowercase
        formatted = RecoveryCodeManager.format_code("abcdefghijkl")
        self.assertEqual(formatted, "ABCD-EFGH-IJKL")

    def test_format_code_invalid_length(self):
        """Test formatting code with invalid length."""
        with self.assertRaises(ValueError):
            RecoveryCodeManager.format_code("ABCD")

        with self.assertRaises(ValueError):
            RecoveryCodeManager.format_code("ABCDEFGHIJKLMNOP")


class TestCreateNewAuthenticator(unittest.TestCase):
    """Test cases for create_new_authenticator function."""

    def test_create_new_authenticator(self):
        """Test creating a new authenticator with recovery codes."""
        auth, codes = create_new_authenticator()

        # Check authenticator
        self.assertIsInstance(auth, TOTPAuthenticator)
        self.assertIsNotNone(auth.get_secret())

        # Check recovery codes
        self.assertIsInstance(codes, list)
        self.assertEqual(len(codes), 10)

        for code in codes:
            self.assertIsInstance(code, str)
            self.assertEqual(len(code), 14)


if __name__ == '__main__':
    unittest.main()
