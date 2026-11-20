"""Twin scoreboard.

Records actual treatment-minus-control *certified* success.

Certified means WITNESS-supported and final-correct. Public-only
correctness is not a learning signal. Each arm writes its own result.
Delta is computed only when both arms for the same task identity are
present. No hard-coded control failure. An unpaired treatment result
is pending, not learning.

Pairing is by pair id when one is given (both arms of one `pair()` run
share it). An unpaired row left behind by an older run, or by a different
pair id, is discarded and logged, never paired with a newer arm. This
staleness rule is credited to NVIDIA Molt's bounded-staleness idea; see
docs/MOLT_EXTRACTION.md.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _board() -> Path:
    return data_root() / "scoreboard.jsonl"


def _pending() -> Path:
    return data_root() / "scoreboard_pending.json"

MAX_PENDING_AGE_S = 3600


def _discarded() -> Path:
    return data_root() / "scoreboard_discarded.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    data_root().mkdir(parents=True, exist_ok=True)

def _load_pending() -> dict[str, Any]:
    if not _pending().exists():
        return {}
    return json.loads(_pending().read_text())

def _save_pending(data: dict[str, Any]) -> None:
    _ensure()
    _pending().write_text(json.dumps(data, indent=2))

def _age_s(ts: str | None, now: datetime) -> float:
    if not ts:
        return float("inf")
    try:
        then = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return float("inf")
    return (now - then).total_seconds()


def _discard(task_id: str, entry: dict[str, Any], reason: str) -> None:
    _ensure()
    row = {"ts": _now(), "task": task_id, "entry": entry, "reason": reason}
    with _discarded().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def prune_pending(max_age_s: float = MAX_PENDING_AGE_S) -> int:
    """Discard unpaired pending rows older than max_age_s. Returns how many."""
    pending = _load_pending()
    now = datetime.now(timezone.utc)
    stale = [k for k, v in pending.items() if _age_s(v.get("ts"), now) > max_age_s]
    for k in stale:
        _discard(k, pending.pop(k), "stale_unpaired")
    if stale:
        _save_pending(pending)
    return len(stale)


def record_arm(
    task_id: str,
    arm: str,
    success: bool,
    *,
    kind: str = "certified",
    pair_id: str | None = None,
    field_version: int | None = None,
    evaluations: int | None = None,
    max_age_s: float = MAX_PENDING_AGE_S,
) -> dict[str, Any] | None:
    """Record one arm. Return the paired delta if both arms are now present.

    `success` must be the certified (WITNESS + final) outcome, not public-only.
    An existing pending entry is discarded instead of paired when its pair id
    differs from this arm's, when it is older than `max_age_s`, or when it
    already holds this arm.
    """
    _ensure()
    pending = _load_pending()
    entry = pending.get(task_id)
    if entry is not None:
        reason = None
        if entry.get("pair_id") != pair_id:
            reason = "pair_id_mismatch"
        elif _age_s(entry.get("ts"), datetime.now(timezone.utc)) > max_age_s:
            reason = "stale_unpaired"
        elif arm in entry:
            reason = "arm_repeated"
        if reason:
            _discard(task_id, entry, reason)
            entry = None
    entry = entry or {}
    entry[arm] = success
    entry["ts"] = _now()
    entry["pair_id"] = pair_id
    if field_version is not None:
        entry[f"{arm}_field_version"] = field_version
    if evaluations is not None:
        entry[f"{arm}_evaluations"] = int(evaluations)
    pending[task_id] = entry
    _save_pending(pending)
    if "treatment" in entry and "control" in entry:
        delta = int(entry["treatment"]) - int(entry["control"])
        row = {
            "ts": _now(),
            "task": task_id,
            "treatment": entry["treatment"],
            "control": entry["control"],
            "delta": delta,
            "kind": kind,
        }
        if pair_id:
            row["pair_id"] = pair_id
        if "treatment_evaluations" in entry and "control_evaluations" in entry:
            row["treatment_evaluations"] = entry["treatment_evaluations"]
            row["control_evaluations"] = entry["control_evaluations"]
            # Positive = the field reached the same outcome with less search.
            row["evaluations_saved"] = entry["control_evaluations"] - entry["treatment_evaluations"]
        if "treatment_field_version" in entry:
            row["field_version"] = entry["treatment_field_version"]
        with _board().open("a") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
        del pending[task_id]
        _save_pending(pending)
        return row
    return None


def recent(n: int = 32) -> list[dict]:
    if not _board().exists():
        return []
    lines = _board().read_text().strip().splitlines()
    return [json.loads(line) for line in lines[-n:] if line]
