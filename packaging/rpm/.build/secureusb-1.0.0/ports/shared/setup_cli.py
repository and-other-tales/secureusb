#!/usr/bin/env python3
"""Shared CLI setup wizard for Windows and macOS ports."""

from __future__ import annotations

import sys
from textwrap import dedent

import qrcode

from src.auth import (
    RecoveryCodeManager,
    SecureStorage,
    create_new_authenticator,
)


def run_cli_setup(platform_label: str = "Desktop") -> int:
    print("=" * 60)
    print(f" SecureUSB {platform_label} Setup ".center(60, "="))
    print("=" * 60)

    storage = SecureStorage()
    if storage.is_configured():
        print("SecureUSB is already configured on this machine.")
        return 0

    authenticator, recovery_codes = create_new_authenticator()
    secret = authenticator.get_secret()
    uri = authenticator.get_provisioning_uri(name="SecureUSB", issuer="SecureUSB")

    print(
        dedent(
            """
            1. Install Google Authenticator (or any TOTP app) on your phone.
            2. Add a new account using the secret below or by scanning the QR.
            """
        ).strip()
    )
    print(f"\nSecret: {secret}\n")

    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    print("\nRecovery codes (store these securely):")
    for idx, code in enumerate(recovery_codes, 1):
        print(f"  {idx:2d}. {code}")

    while True:
        user_code = input("\nEnter the current 6-digit TOTP code to confirm setup: ").strip()
        if len(user_code) != 6 or not user_code.isdigit():
            print("Please enter a 6-digit numeric code.")
            continue

        if authenticator.verify_code(user_code):
            break

        print("Code did not match. Try again; it changes every 30 seconds.")

    hashed_codes = [RecoveryCodeManager.hash_code(code) for code in recovery_codes]
    if not storage.save_auth_data(secret, hashed_codes):
        print("Failed to persist authentication data.", file=sys.stderr)
        return 1

    print("\n✓ SecureUSB credentials saved successfully.")
    print(f"Config directory: {storage.config_dir}")
    return 0
