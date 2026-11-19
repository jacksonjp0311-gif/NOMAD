"""Cellular automata on the Bitwork field.

Local rules evolve sparse binary packets.
Multiple rules. The sleep phase can try more than one and keep what the twin prefers.
Integer only.
"""
from __future__ import annotations

from .weights import Packet, load_packets, append_packet

RULES = {
    "majority": lambda n, c: c + 1 if n >= 3 and c > 0 else (c if n == 2 else max(0, c - 1)),
    "growth": lambda n, c: c + 1 if n >= 1 and c > 0 else max(0, c - 1),
    "decay": lambda n, c: c if n >= 2 else max(0, c - 1),
    "stabilize": lambda n, c: c if n == 2 else (c + 1 if n > 2 else max(0, c - 1)),
}

def evolve(steps: int = 1, rule_name: str = "majority") -> int:
    """One or more CA steps under a named rule. Returns packets written."""
    rule = RULES.get(rule_name, RULES["majority"])
    packets = load_packets()
    if not packets:
        return 0
    written = 0
    for _ in range(steps):
        next_packets = []
        for p in packets:
            neighbors = sum(1 for other in packets if other is not p and p.overlap(other.bits) > 0)
            new_count = rule(neighbors, p.count)
            if new_count > 0:
                next_packets.append(Packet(p.bits, new_count, p.label, p.receipt))
        packets = next_packets
    for p in packets:
        append_packet(p)
        written += 1
    return written

def try_rules(steps: int = 1) -> dict[str, int]:
    """Run every rule once and return packet counts written."""
    results = {}
    for name in RULES:
        results[name] = evolve(steps=steps, rule_name=name)
    return results

def seed(bits: set[int], count: int = 1, label: str = "seed") -> None:
    append_packet(Packet(bits, count, label))
