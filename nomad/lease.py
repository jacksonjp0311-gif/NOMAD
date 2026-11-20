"""Single-body lease. Only one host writes the field at a time.

``data/lease.json`` holds the host id and a heartbeat timestamp. A host may
take over only when the lease is released or its heartbeat is older than
the stale window. The lease travels through git like the rest of the state,
so it works across a GitHub runner, a desktop, or any CPU host.
"""
from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root

STALE_MIN = 30


def path() -> Path:
    return data_root() / "lease.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def host_id() -> str:
    if os.environ.get("NOMAD_HOST_ID"):
        return os.environ["NOMAD_HOST_ID"]
    if os.environ.get("GITHUB_RUN_ID"):
        return f"gh-{os.environ['GITHUB_RUN_ID']}"
    return f"{platform.node() or 'host'}-{os.getpid()}"


def read() -> dict[str, Any] | None:
    try:
        return json.loads(path().read_text()) if path().exists() else None
    except json.JSONDecodeError:
        return None


def age_min(lease: dict[str, Any] | None) -> float | None:
    if not lease or not lease.get("heartbeat"):
        return None
    try:
        t = datetime.strptime(lease["heartbeat"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (_now() - t).total_seconds() / 60.0


def alive(lease: dict[str, Any] | None = None, stale_min: float = STALE_MIN) -> bool:
    lease = read() if lease is None else lease
    if not lease or lease.get("released"):
        return False
    a = age_min(lease)
    return a is not None and a < stale_min


def held_by_other(me: str, stale_min: float = STALE_MIN) -> bool:
    lease = read()
    return alive(lease, stale_min) and lease.get("host") != me


def write(me: str, *, started: str | None = None, released: bool = False, **extra: Any) -> dict[str, Any]:
    prev = read() or {}
    row = {"schema": "nomad.lease.v1", "host": me,
           "started": started or (prev.get("started") if prev.get("host") == me else None) or _fmt(_now()),
           "heartbeat": _fmt(_now()), "stale_after_min": STALE_MIN, "released": released, **extra}
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(row, indent=2))
    return row
