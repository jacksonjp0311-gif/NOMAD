"""Society layer absorbed from Agent Colony.

Minimal registry, bus, fitness, and gate.
Roles enter and leave. Messages deliver. Fitness updates from outcomes.
Gate rejects what fails. Durable promotion still waits for human authorize.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOCIETY = ROOT / "data" / "society"
REGISTRY = SOCIETY / "registry.json"
BUS = SOCIETY / "bus.jsonl"
FITNESS = SOCIETY / "fitness.json"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure() -> None:
    SOCIETY.mkdir(parents=True, exist_ok=True)

@dataclass
class Role:
    name: str
    skills: dict[str, float] = field(default_factory=dict)
    contribution: float = 0.0
    inbox: list[dict] = field(default_factory=list)

def load_registry() -> dict[str, Role]:
    _ensure()
    if not REGISTRY.exists():
        return {
            "spark": Role("spark", {"propose": 1.0}),
            "keeper": Role("keeper", {"record": 1.0}),
        }
    data = json.loads(REGISTRY.read_text())
    return {k: Role(**v) for k, v in data.items()}

def save_registry(reg: dict[str, Role]) -> None:
    _ensure()
    REGISTRY.write_text(json.dumps({k: vars(v) for k, v in reg.items()}, indent=2))

def post(role: str, message: dict[str, Any]) -> None:
    _ensure()
    row = {"to": role, "message": message, "ts": _now()}
    with BUS.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    reg = load_registry()
    if role in reg:
        reg[role].inbox.append(row)
        save_registry(reg)

def load_fitness() -> dict[str, float]:
    _ensure()
    if not FITNESS.exists():
        return {"success": 0.0, "cycles": 0.0}
    return json.loads(FITNESS.read_text())

def update_fitness(success: bool) -> None:
    fit = load_fitness()
    fit["cycles"] = fit.get("cycles", 0) + 1
    if success:
        fit["success"] = fit.get("success", 0) + 1
    FITNESS.write_text(json.dumps(fit, indent=2))

def gate(outcome: dict[str, Any]) -> dict[str, Any]:
    """Simple gate. Public success passes. Everything else is candidate or reject."""
    if outcome.get("public_correct"):
        return {"pass": True, "reason": "public_correct"}
    return {"pass": False, "reason": outcome.get("abstained") or "no_success"}
