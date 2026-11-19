"""Bitwork weight packets.

Sparse binary packets that accumulate learned knowledge.
Each packet is a set of bit positions plus a count.
Packets can be split, merged, and queried by integer overlap.
The field is the living weight store. No floating-point neural weights.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PACKETS = ROOT / "data" / "weights" / "packets.jsonl"
BITS = 4096

def _ensure() -> None:
    PACKETS.parent.mkdir(parents=True, exist_ok=True)

@dataclass
class Packet:
    bits: set[int]
    count: int = 1
    label: str = ""

    def overlap(self, other: set[int]) -> int:
        return len(self.bits & other)

    def as_dict(self) -> dict[str, Any]:
        return {"bits": sorted(self.bits), "count": self.count, "label": self.label}

def append_packet(packet: Packet) -> None:
    _ensure()
    with PACKETS.open("a") as f:
        f.write(json.dumps(packet.as_dict(), separators=(",", ":")) + "\n")

def load_packets() -> list[Packet]:
    if not PACKETS.exists():
        return []
    packets = []
    with PACKETS.open() as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                packets.append(Packet(set(row["bits"]), row.get("count", 1), row.get("label", "")))
    return packets

def readout(query_bits: set[int], k: int = 16) -> list[dict[str, Any]]:
    """Fixed readout. Top-k packets by integer overlap, weighted by count."""
    scored = [(p.overlap(query_bits) * p.count, p) for p in load_packets()]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"overlap": ov, "count": p.count, "label": p.label, "size": len(p.bits)}
        for ov, p in scored[:k]
    ]

def split_packet(packet: Packet, parts: int = 2) -> list[Packet]:
    """Split a packet into smaller packets that share the same count."""
    if parts < 2 or not packet.bits:
        return [packet]
    items = list(packet.bits)
    size = max(1, len(items) // parts)
    out = []
    for i in range(0, len(items), size):
        chunk = set(items[i:i + size])
        if chunk:
            out.append(Packet(chunk, packet.count, packet.label))
    return out

def merge_similar(threshold: int = 32) -> int:
    """Merge packets that share high overlap. Returns number of merges."""
    packets = load_packets()
    if len(packets) < 2:
        return 0
    merged = 0
    used = [False] * len(packets)
    new_packets = []
    for i, p in enumerate(packets):
        if used[i]:
            continue
        group = [p]
        used[i] = True
        for j in range(i + 1, len(packets)):
            if used[j]:
                continue
            if p.overlap(packets[j].bits) >= threshold:
                group.append(packets[j])
                used[j] = True
        if len(group) > 1:
            bits = set()
            count = 0
            for g in group:
                bits |= g.bits
                count += g.count
            new_packets.append(Packet(bits, count, group[0].label))
            merged += len(group) - 1
        else:
            new_packets.append(p)
    if merged:
        PACKETS.write_text("".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in new_packets))
    return merged

def accumulate(query_bits: set[int], success: bool, label: str = "") -> None:
    """Add or reinforce a packet from an outcome."""
    if not success:
        return
    append_packet(Packet(query_bits, 1, label))
    merge_similar()
