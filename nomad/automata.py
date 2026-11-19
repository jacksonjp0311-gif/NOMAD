"""Cellular automata on the Bitwork field.

Local rules evolve sparse binary packets.
Each rule is evaluated on an independent snapshot.
Only the rule that produces the highest survival count is committed.
Integer only.
"""
from __future__ import annotations

import copy
from .weights import Packet, load_packets, append_packet

RULES = {
    "majority": lambda n, c: c + 1 if n >= 3 and c > 0 else (c if n == 2 else max(0, c - 1)),
    "growth": lambda n, c: c + 1 if n >= 1 and c > 0 else max(0, c - 1),
    "decay": lambda n, c: c if n >= 2 else max(0, c - 1),
    "stabilize": lambda n, c: c if n == 2 else (c + 1 if n > 2 else max(0, c - 1)),
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

def try_rules(steps: int = 1) -> dict[str, int]:
    """Evaluate every rule on an independent snapshot. Commit only the best."""
    original = load_packets()
    if not original:
        return {}
    results = {}
    best_name = None
    best_count = -1
    best_packets = None
    for name, rule in RULES.items():
        evolved = _apply_rule(original, rule, steps)
        count = len(evolved)
        results[name] = count
        if count > best_count:
            best_count = count
            best_name = name
            best_packets = evolved
    if best_packets is not None and best_name is not None:
        # Clear and rewrite with the winner only
        from pathlib import Path
        import json
        path = Path(__file__).resolve().parent.parent / "data" / "weights" / "packets.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in best_packets))
        results["winner"] = best_name
    return results

def seed(bits: set[int], count: int = 1, label: str = "seed") -> None:
    append_packet(Packet(bits, count, label))
