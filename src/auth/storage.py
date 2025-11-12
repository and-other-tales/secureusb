#!/usr/bin/env python3
"""
Secure Storage Module for SecureUSB

Handles encrypted storage of TOTP secrets and recovery codes.
Uses cryptography library with Fernet symmetric encryption.
"""

import json
import os
import stat
from pathlib import Path
from typing import List, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from src.utils.paths import resolve_config_dir


class SecureStorage:
    """Manages encrypted storage of authentication credentials."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize secure storage.

        Args:
            config_dir: Configuration directory path. If None, uses the shared SecureUSB config dir.
        """
        if config_dir is None:
            self.config_dir = resolve_config_dir()
        else:
            self.config_dir = Path(config_dir)

        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (700 = owner only)
        os.chmod(self.config_dir, stat.S_IRWXU)

        # File paths
        self.auth_file = self.config_dir / "auth.enc"
        self.key_file = self.config_dir / ".key"
        self.salt_file = self.config_dir / ".salt"

        # Initialize encryption
        self._init_encryption()

    def _init_encryption(self):
        """Initialize encryption keys and cipher."""
        # Generate or load salt
        if self.salt_file.exists():
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
        else:
            salt = os.urandom(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            os.chmod(self.salt_file, stat.S_IRUSR | stat.S_IWUSR)

        # Derive key from machine-specific data
        # Using machine-id as password source (unique per installation)
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
        except FileNotFoundError:
            # Fallback for systems without machine-id
            machine_id = str(os.getuid()) + str(self.config_dir)

        # Derive encryption key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))

        self.cipher = Fernet(key)

    def save_auth_data(self, secret: str, recovery_codes: List[str]) -> bool:
        """
        Save TOTP secret and recovery codes to encrypted storage.

        Args:
            secret: Base32-encoded TOTP secret
            recovery_codes: List of hashed recovery codes

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create data structure
            data = {
                'totp_secret': secret,
                'recovery_codes': recovery_codes,
                'version': 1
            }

            # Serialize to JSON
            json_data = json.dumps(data)

            # Encrypt
            encrypted = self.cipher.encrypt(json_data.encode())

            # Write to file
            with open(self.auth_file, 'wb') as f:
                f.write(encrypted)

            # Set restrictive permissions (600 = owner read/write only)
            os.chmod(self.auth_file, stat.S_IRUSR | stat.S_IWUSR)

            return True

        except Exception as e:
            print(f"Error saving auth data: {e}")
            return False

    def load_auth_data(self) -> Optional[Dict]:
        """
        Load TOTP secret and recovery codes from encrypted storage.

        Returns:
            Dictionary with 'totp_secret' and 'recovery_codes', or None if not found
        """
        if not self.auth_file.exists():
            return None

        try:
            # Read encrypted file
            with open(self.auth_file, 'rb') as f:
                encrypted = f.read()

            # Decrypt
            decrypted = self.cipher.decrypt(encrypted)

            # Parse JSON
            data = json.loads(decrypted.decode())

            return {
                'totp_secret': data['totp_secret'],
                'recovery_codes': data['recovery_codes']
            }

        except Exception as e:
            print(f"Error loading auth data: {e}")
            return None

    def is_configured(self) -> bool:
        """
        Check if authentication is already configured.

        Returns:
            True if auth.enc exists, False otherwise
        """
        return self.auth_file.exists()

    def remove_recovery_code(self, code_hash: str) -> bool:
        """
        Remove a used recovery code from storage.

        Args:
            code_hash: SHA-256 hash of the used recovery code

        Returns:
            True if successful, False otherwise
        """
        data = self.load_auth_data()
        if data is None:
            return False

        try:
            # Remove the code from the list
            if code_hash in data['recovery_codes']:
                data['recovery_codes'].remove(code_hash)

                # Save updated data
                return self.save_auth_data(
                    data['totp_secret'],
                    data['recovery_codes']
                )

            return False

        except Exception as e:
            print(f"Error removing recovery code: {e}")
            return False

    def get_remaining_recovery_codes_count(self) -> int:
        """
        Get the number of remaining unused recovery codes.

        Returns:
            Number of recovery codes, or 0 if error
        """
        data = self.load_auth_data()
        if data is None:
            return 0

        return len(data['recovery_codes'])

    def reset_auth(self) -> bool:
        """
        Remove all authentication data (for reconfiguration).

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.auth_file.exists():
                self.auth_file.unlink()
            return True
        except Exception as e:
            print(f"Error resetting auth: {e}")
            return False

    def export_config(self, export_path: Path) -> bool:
        """
        Export encrypted configuration to a file (for backup).

        Args:
            export_path: Path to export file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.auth_file.exists():
                return False

            # Read encrypted data
            with open(self.auth_file, 'rb') as f:
                encrypted_data = f.read()

            # Read salt
            with open(self.salt_file, 'rb') as f:
                salt_data = f.read()

            # Also include salt for proper decryption on restore
            export_data = {
                'auth_data': base64.b64encode(encrypted_data).decode(),
                'salt': base64.b64encode(salt_data).decode(),
                'version': 1
            }

            # Write to export file
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            # Set restrictive permissions
            os.chmod(export_path, stat.S_IRUSR | stat.S_IWUSR)

            return True

        except Exception as e:
            print(f"Error exporting config: {e}")
            return False

    def import_config(self, import_path: Path) -> bool:
        """
        Import encrypted configuration from a backup file.

        Args:
            import_path: Path to import file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read export file
            with open(import_path, 'r') as f:
                export_data = json.load(f)

            # Restore salt
            salt = base64.b64decode(export_data['salt'])
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            os.chmod(self.salt_file, stat.S_IRUSR | stat.S_IWUSR)

            # Restore auth data
            encrypted_data = base64.b64decode(export_data['auth_data'])
            with open(self.auth_file, 'wb') as f:
                f.write(encrypted_data)
            os.chmod(self.auth_file, stat.S_IRUSR | stat.S_IWUSR)

            # Reinitialize encryption with new salt
            self._init_encryption()

            return True

        except Exception as e:
            print(f"Error importing config: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    import sys
    from totp import TOTPAuthenticator, RecoveryCodeManager

    print("=== SecureUSB Secure Storage Test ===\n")

    # Create storage instance
    storage = SecureStorage()

    if storage.is_configured():
        print("Existing configuration found!")

        # Load existing data
        data = storage.load_auth_data()
        if data:
            print(f"TOTP Secret: {data['totp_secret'][:8]}..." )
            print(f"Recovery Codes: {len(data['recovery_codes'])} remaining")

            # Test authenticator with loaded secret
            auth = TOTPAuthenticator(data['totp_secret'])
            print(f"Current TOTP Code: {auth.get_current_code()}")
    else:
        print("No existing configuration. Creating new...")

        # Create new authenticator and recovery codes
        auth = TOTPAuthenticator()
        codes = RecoveryCodeManager.generate_codes()

        # Hash recovery codes for storage
        hashed_codes = [RecoveryCodeManager.hash_code(code) for code in codes]

        # Save to encrypted storage
        if storage.save_auth_data(auth.get_secret(), hashed_codes):
            print("✓ Authentication data saved successfully!")
            print(f"\nSecret: {auth.get_secret()}")
            print(f"Current Code: {auth.get_current_code()}")
            print(f"\nRecovery Codes (save these somewhere safe!):")
            for i, code in enumerate(codes, 1):
                print(f"  {i:2d}. {code}")
        else:
            print("✗ Failed to save authentication data")
            sys.exit(1)

    print(f"\nConfig directory: {storage.config_dir}")
    print(f"Configured: {storage.is_configured()}")
    print(f"Remaining recovery codes: {storage.get_remaining_recovery_codes_count()}")
