#!/usr/bin/env python3
"""CLI setup wizard for macOS port."""

from __future__ import annotations

from . import path_setup  # noqa: F401
from ports.shared.setup_cli import run_cli_setup


if __name__ == "__main__":
    raise SystemExit(run_cli_setup("macOS"))
