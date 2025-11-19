#!/usr/bin/env python3
"""
TOTP Authentication Module for SecureUSB

Handles Time-based One-Time Password generation and verification
using pyotp, compatible with Google Authenticator and other TOTP apps.
"""

import pyotp
import secrets
import hashlib
import time
from typing import List, Tuple, Optional

# Constants
TOTP_CODE_LENGTH = 6
TOTP_TIME_WINDOW_SECONDS = 30
TOTP_MAX_VALIDATION_WINDOW = 5
RECOVERY_CODE_LENGTH = 12
RECOVERY_CODE_FORMAT_SEGMENT_LENGTH = 4
RECOVERY_CODE_MIN_COUNT = 1
RECOVERY_CODE_MAX_COUNT = 100


class TOTPAuthenticator:
    """Manages TOTP authentication for USB device authorization."""

    def __init__(self, secret: Optional[str] = None):
        """
        Initialize TOTP authenticator.

        Args:
            secret: Base32-encoded secret key. If None, a new one is generated.
        """
        if secret:
            self.secret = secret
        else:
            self.secret = pyotp.random_base32()

        self.totp = pyotp.TOTP(self.secret)
        self._last_used_code = None
        self._last_used_time = 0

    def get_secret(self) -> str:
        """
        Get the Base32-encoded secret key.

        Returns:
            The secret key as a string.
        """
        return self.secret

    def get_provisioning_uri(self, name: str = "SecureUSB", issuer: str = None) -> str:
        """
        Generate a provisioning URI for QR code generation.

        Args:
            name: Account name to display in authenticator app
            issuer: Issuer name (defaults to hostname)

        Returns:
            Provisioning URI string for QR code
        """
        if issuer is None:
            import socket
            issuer = socket.gethostname()

        return self.totp.provisioning_uri(name=name, issuer_name=issuer)

    def verify_code(self, code: str, window: int = 1) -> bool:
        """
        Verify a TOTP code.

        Args:
            code: The 6-digit TOTP code to verify
            window: Number of time windows to check (past and future)

        Returns:
            True if code is valid, False otherwise
        """
        # Validate window parameter to prevent timing attacks
        window = max(0, min(TOTP_MAX_VALIDATION_WINDOW, window))

        # Remove any spaces or dashes from input
        code = code.replace(' ', '').replace('-', '')

        # Check if code is 6 digits
        if not code.isdigit() or len(code) != TOTP_CODE_LENGTH:
            return False

        # Prevent code reuse within the same time window
        current_time = time.time()
        if code == self._last_used_code and (current_time - self._last_used_time) < TOTP_TIME_WINDOW_SECONDS:
            return False

        # Verify the code
        is_valid = self.totp.verify(code, valid_window=window)

        if is_valid:
            self._last_used_code = code
            self._last_used_time = current_time

        return is_valid

    def get_current_code(self) -> str:
        """
        Generate the current TOTP code.

        Note: This should only be used for testing/debugging.

        Returns:
            The current 6-digit TOTP code
        """
        return self.totp.now()

    def get_time_remaining(self) -> int:
        """
        Get seconds remaining until the current code expires.

        Returns:
            Seconds until next code generation (0-30)
        """
        return TOTP_TIME_WINDOW_SECONDS - (int(time.time()) % TOTP_TIME_WINDOW_SECONDS)


class RecoveryCodeManager:
    """Manages one-time recovery codes for emergency access."""

    @staticmethod
    def generate_codes(count: int = 10) -> List[str]:
        """
        Generate cryptographically secure recovery codes.

        Args:
            count: Number of recovery codes to generate (1-100)

        Returns:
            List of recovery codes in format XXXX-XXXX-XXXX

        Raises:
            TypeError: If count is not an integer
        """
        # Validate type
        if not isinstance(count, int):
            raise TypeError(f"count must be an integer, got {type(count).__name__}")

        # Validate count to prevent resource exhaustion
        count = max(RECOVERY_CODE_MIN_COUNT, min(RECOVERY_CODE_MAX_COUNT, count))

        codes = []
        for _ in range(count):
            # Generate 12 random characters using base32 alphabet
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567') for _ in range(RECOVERY_CODE_LENGTH))
            # Format as XXXX-XXXX-XXXX
            seg_len = RECOVERY_CODE_FORMAT_SEGMENT_LENGTH
            formatted = f"{code[0:seg_len]}-{code[seg_len:seg_len*2]}-{code[seg_len*2:seg_len*3]}"
            codes.append(formatted)

        return codes

    @staticmethod
    def hash_code(code: str) -> str:
        """
        Hash a recovery code for secure storage.

        Args:
            code: Recovery code to hash

        Returns:
            SHA-256 hash of the code
        """
        # Remove dashes and convert to uppercase
        clean_code = code.replace('-', '').upper()
        # Hash with SHA-256
        return hashlib.sha256(clean_code.encode()).hexdigest()

    @staticmethod
    def verify_code(code: str, hashed_code: str) -> bool:
        """
        Verify a recovery code against its hash.

        Args:
            code: Recovery code to verify
            hashed_code: SHA-256 hash to compare against

        Returns:
            True if code matches hash, False otherwise
        """
        return RecoveryCodeManager.hash_code(code) == hashed_code

    @staticmethod
    def format_code(code: str) -> str:
        """
        Format a recovery code to standard format.

        Args:
            code: Raw recovery code (may have spaces, dashes, mixed case)

        Returns:
            Formatted code as XXXX-XXXX-XXXX

        Raises:
            TypeError: If code is not a string
            ValueError: If code is not 12 alphanumeric characters
        """
        # Validate type
        if not isinstance(code, str):
            raise TypeError(f"code must be a string, got {type(code).__name__}")

        # Remove all non-alphanumeric characters and convert to uppercase
        clean = ''.join(c for c in code.upper() if c.isalnum())

        # Check length
        if len(clean) != RECOVERY_CODE_LENGTH:
            raise ValueError(f"Recovery code must be {RECOVERY_CODE_LENGTH} characters, got {len(clean)}")

        # Format with dashes
        seg_len = RECOVERY_CODE_FORMAT_SEGMENT_LENGTH
        return f"{clean[0:seg_len]}-{clean[seg_len:seg_len*2]}-{clean[seg_len*2:seg_len*3]}"


def create_new_authenticator() -> Tuple[TOTPAuthenticator, List[str]]:
    """
    Create a new TOTP authenticator with recovery codes.

    Returns:
        Tuple of (TOTPAuthenticator instance, list of recovery codes)
    """
    authenticator = TOTPAuthenticator()
    recovery_codes = RecoveryCodeManager.generate_codes()
    return authenticator, recovery_codes


# Example usage and testing
if __name__ == "__main__":
    print("=== SecureUSB TOTP Authentication Test ===\n")

    # Create new authenticator
    auth, codes = create_new_authenticator()

    print(f"Secret Key: {auth.get_secret()}")
    print(f"Current Code: {auth.get_current_code()}")
    print(f"Time Remaining: {auth.get_time_remaining()}s")
    print(f"\nProvisioning URI:\n{auth.get_provisioning_uri()}\n")

    print("Recovery Codes:")
    for i, code in enumerate(codes, 1):
        hashed = RecoveryCodeManager.hash_code(code)
        print(f"{i:2d}. {code} -> {hashed[:16]}...")

    # Test verification
    current = auth.get_current_code()
    print(f"\nTesting verification with current code: {current}")
    print(f"Verification result: {auth.verify_code(current)}")

    # Test recovery code
    test_code = codes[0]
    hashed = RecoveryCodeManager.hash_code(test_code)
    print(f"\nTesting recovery code: {test_code}")
    print(f"Verification result: {RecoveryCodeManager.verify_code(test_code, hashed)}")
