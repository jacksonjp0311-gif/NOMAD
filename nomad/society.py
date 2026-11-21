"""Society layer absorbed from Agent Colony.

Minimal registry, bus, fitness, and gate.
Roles enter and leave. Messages deliver. Fitness updates from outcomes.
Gate rejects what fails. Packet updates require a WITNESS-supported, final-correct treatment outcome. They are not a general skill promotion. External or irreversible actions remain separately gated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root


def _society() -> Path:
    return data_root() / "society"


def _registry() -> Path:
    return _society() / "registry.json"


def _bus() -> Path:
    return _society() / "bus.jsonl"


def _fitness() -> Path:
    return _society() / "fitness.json"

INBOX_KEEP = 200  # newest messages kept per role; the full stream lives in bus.jsonl (trimmed by retention)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    _society().mkdir(parents=True, exist_ok=True)

@dataclass
class Role:
    name: str
    skills: dict[str, float] = field(default_factory=dict)
    contribution: float = 0.0
    inbox: list[dict] = field(default_factory=list)

def load_registry() -> dict[str, Role]:
    _ensure()
    if not _registry().exists():
        return {
            "spark": Role("spark", {"propose": 1.0}),
            "keeper": Role("keeper", {"record": 1.0}),
        }
    data = json.loads(_registry().read_text())
    return {k: Role(**v) for k, v in data.items()}

def save_registry(reg: dict[str, Role]) -> None:
    _ensure()
    _registry().write_text(json.dumps({k: vars(v) for k, v in reg.items()}, separators=(",", ":")))


def trim_registry(keep: int = INBOX_KEEP) -> int:
    """Cap every role inbox at its newest ``keep`` rows; return rows dropped.

    Unbounded inboxes pushed data/society/registry.json past GitHub's 100 MB
    file limit on Nov 21 2026, so every body checkpoint push was rejected."""
    if not _registry().exists():
        return 0
    reg = load_registry()
    dropped = 0
    for r in reg.values():
        if len(r.inbox) > keep:
            dropped += len(r.inbox) - keep
            r.inbox = r.inbox[-keep:]
    if dropped:
        save_registry(reg)
    return dropped

def post(role: str, message: dict[str, Any]) -> None:
    _ensure()
    row = {"to": role, "message": message, "ts": _now()}
    with _bus().open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    reg = load_registry()
    if role in reg:
        reg[role].inbox.append(row)
        reg[role].inbox = reg[role].inbox[-INBOX_KEEP:]
        save_registry(reg)

def load_fitness() -> dict[str, float]:
    _ensure()
    if not _fitness().exists():
        return {"success": 0.0, "cycles": 0.0}
    return json.loads(_fitness().read_text())

def update_fitness(success: bool) -> None:
    fit = load_fitness()
    fit["cycles"] = fit.get("cycles", 0) + 1
    if success:
        fit["success"] = fit.get("success", 0) + 1
    _fitness().write_text(json.dumps(fit, indent=2))

def gate(outcome: dict[str, Any]) -> dict[str, Any]:
    """Certify only what WITNESS supports and the final split confirms.

    Public-example success is recorded but is not a pass. Search and memory
    do not certify. An empty or missing withheld split cannot pass.
    """
    if outcome.get("witness_supported") and outcome.get("final_correct"):
        return {"pass": True, "reason": "witness_and_final"}
    if outcome.get("public_correct"):
        return {"pass": False, "reason": "public_only_not_certified"}
    return {"pass": False, "reason": outcome.get("abstained") or "no_success"}
