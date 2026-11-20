"""Resolvable data root for the continuous field.

Set NOMAD_DATA to a directory to redirect packets, logs, and scoreboard
writes. Tests use this so they never mutate the repository's live field.
When unset, data lives under the package root at data/.
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    override = os.environ.get("NOMAD_DATA")
    if override:
        return Path(override)
    return PACKAGE_ROOT / "data"
