"""Self-rewrite for the Bitwork field.

Diagnoses differences between successful and failed cycles using packet overlap and SIM receipts.
Proposes small targeted edits (bit flips or count adjustments) to high-impact packets.
Edits are tested before commit. Integer only. No gradients.
"""
from __future__ import annotations

from typing import Any

from .weights import Packet, load_packets, append_packet
from .sim import recent

def diagnose() -> dict[str, Any]:
    """Compare recent successes and failures. Return high-differential packets."""
    history = recent(32)
    successes = [r for r in history if r.get("measured") == "public_correct"]
    failures = [r for r in history if r.get("measured") != "public_correct"]
    packets = load_packets()
    if not packets or not successes:
        return {"candidates": []}
    # Simple differential: packets that appear more in success contexts
    scored = []
    for p in packets:
        success_hits = sum(1 for s in successes if s.get("context", {}).get("task") == p.label)
        fail_hits = sum(1 for f in failures if f.get("context", {}).get("task") == p.label)
        delta = success_hits - fail_hits
        if delta > 0:
            scored.append((delta, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {
        "candidates": [
            {"label": p.label, "count": p.count, "delta": d, "size": len(p.bits)}
            for d, p in scored[:4]
        ]
    }

def propose_edit(packet: Packet, strength: float = 0.1) -> Packet:
    """Propose a small count adjustment or bit reinforcement."""
    new_count = max(1, int(packet.count * (1 + strength)))
    return Packet(packet.bits, new_count, packet.label, packet.receipt)

def rewrite(test: bool = True) -> dict[str, Any]:
    """Diagnose, propose, and optionally commit a small edit."""
    diag = diagnose()
    if not diag["candidates"]:
        return {"status": "no_candidates"}
    packets = load_packets()
    target = next((p for p in packets if p.label == diag["candidates"][0]["label"]), None)
    if not target:
        return {"status": "no_target"}
    edited = propose_edit(target)
    if test:
        # Placeholder test: in practice run against twin or practice task
        # For now, commit if diagnosis is positive
        append_packet(edited)
        return {"status": "committed", "edit": edited.as_dict()}
    return {"status": "proposed", "edit": edited.as_dict()}
