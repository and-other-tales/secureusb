"""Ensure the root SecureUSB package can be imported when running from /windows."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_on_path():
    current_file = Path(__file__).resolve()
    repo_root = current_file.parents[2]
    src_dir = repo_root / "src"
    ports_dir = repo_root / "ports"

    for candidate in (repo_root, src_dir, ports_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


_ensure_repo_on_path()
