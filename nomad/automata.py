"""Cellular automata on the Bitwork field.

Local rules evolve sparse binary packets.
Each rule is evaluated on an independent snapshot.
No-op is always an eligible winner.
A rule commits only if it preserves every packet that has a successful receipt
and does not reduce the count of successful packets.
Integer only.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .weights import Packet, load_packets

RULES = {
    "majority": lambda n, c: c + 1 if n >= 3 and c > 0 else (c if n == 2 else max(0, c - 1)),
    "growth": lambda n, c: c + 1 if n >= 1 and c > 0 else max(0, c - 1),
    "decay": lambda n, c: c if n >= 2 else max(0, c - 1),
    "stabilize": lambda n, c: c if n == 2 else (c + 1 if n > 2 else max(0, c - 1)),
}

def _successful(packets: list[Packet]) -> set[str]:
    return {
        p.label
        for p in packets
        if p.receipt.get("measured") == "public_correct" and p.label
    }

def _apply_rule(packets: list[Packet], rule, steps: int = 1) -> list[Packet]:
    current = copy.deepcopy(packets)
    for _ in range(steps):
        next_packets = []
        for p in current:
            neighbors = sum(1 for other in current if other is not p and p.overlap(other.bits) > 0)
            new_count = rule(neighbors, p.count)
            if new_count > 0:
                next_packets.append(Packet(p.bits, new_count, p.label, p.receipt))
        current = next_packets
    return current

def try_rules(steps: int = 1) -> dict:
    """Evaluate every rule on an independent snapshot. Prefer no-op."""
    original = load_packets()
    if not original:
        return {}
    original_success = _successful(original)
    results = {"noop": len(original)}
    best_name = "noop"
    best_packets = original
    for name, rule in RULES.items():
        evolved = _apply_rule(original, rule, steps)
        evolved_success = _successful(evolved)
        results[name] = len(evolved)
        # Only consider a rule if it preserves every successful label
        if original_success.issubset(evolved_success) and len(evolved) >= len(original):
            best_name = name
            best_packets = evolved
    if best_name != "noop":
        path = Path(__file__).resolve().parent.parent / "data" / "weights" / "packets.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in best_packets))
    results["winner"] = best_name
    return results

def seed(bits: set[int], count: int = 1, label: str = "seed") -> None:
    from .weights import append_packet
    append_packet(Packet(bits, count, label))
