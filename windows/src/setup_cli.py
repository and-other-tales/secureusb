#!/usr/bin/env python3
"""
Simple CLI setup wizard for Windows that mirrors the Linux GTK workflow.
"""

from __future__ import annotations

import sys
import sys

from . import path_setup  # noqa: F401
from ports.shared.setup_cli import run_cli_setup


if __name__ == "__main__":
    raise SystemExit(run_cli_setup("Windows"))
