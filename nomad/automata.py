"""Cellular automata on the Bitwork field.

Local rules evolve sparse binary packets.
A packet is a neighborhood. The next state is the overlap and count under a fixed rule.
No floating-point. Integer only.
"""
from __future__ import annotations

from .weights import Packet, load_packets, append_packet

def rule(neighbors: int, count: int) -> int:
    """Simple majority-style rule."""
    if neighbors >= 3 and count > 0:
        return count + 1
    if neighbors == 2:
        return count
    return max(0, count - 1)

def evolve(steps: int = 1) -> int:
    """One or more CA steps. Returns number of packets written."""
    packets = load_packets()
    if not packets:
        return 0
    written = 0
    for _ in range(steps):
        next_packets = []
        for p in packets:
            # Neighborhood is the packet itself plus any overlapping packets
            neighbors = sum(1 for other in packets if other is not p and p.overlap(other.bits) > 0)
            new_count = rule(neighbors, p.count)
            if new_count > 0:
                next_packets.append(Packet(p.bits, new_count, p.label))
        packets = next_packets
    for p in packets:
        append_packet(p)
        written += 1
    return written

def seed(bits: set[int], count: int = 1, label: str = "seed") -> None:
    append_packet(Packet(bits, count, label))
