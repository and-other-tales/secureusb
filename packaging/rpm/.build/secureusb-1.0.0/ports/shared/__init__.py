"""Shared helpers for SecureUSB platform-specific ports."""

__all__ = ["AuthorizationDialog", "run_cli_setup"]


def __getattr__(name):
    if name == "AuthorizationDialog":
        from .dialog import AuthorizationDialog as _Dialog
        return _Dialog
    if name == "run_cli_setup":
        from .setup_cli import run_cli_setup as _run_cli_setup
        return _run_cli_setup
    raise AttributeError(f"module 'ports.shared' has no attribute {name!r}")
