"""Bitwork weight packets.

Sparse binary packets that accumulate learned knowledge.
Each packet is a set of bit positions plus a count and a SIM receipt.
Packets can be split, merged, and queried by integer overlap.
The field is the living weight store. No floating-point neural weights.

SIM recording is the caller's responsibility. accumulate does not record.
reinforce increases the count of a matching domain packet on success.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    receipt: dict[str, Any] = field(default_factory=dict)

    def overlap(self, other: set[int]) -> int:
        return len(self.bits & other)

    def as_dict(self) -> dict[str, Any]:
        return {
            "bits": sorted(self.bits),
            "count": self.count,
            "label": self.label,
            "receipt": self.receipt,
        }

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
                packets.append(
                    Packet(
                        set(row["bits"]),
                        row.get("count", 1),
                        row.get("label", ""),
                        row.get("receipt", {}),
                    )
                )
    return packets

def _write(packets: list[Packet]) -> None:
    _ensure()
    PACKETS.write_text("".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in packets))

def readout(query_bits: set[int], k: int = 16) -> list[dict[str, Any]]:
    """Fixed readout. Top-k packets by integer overlap, weighted by count."""
    scored = [(p.overlap(query_bits) * p.count, p) for p in load_packets()]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "overlap": ov,
            "count": p.count,
            "label": p.label,
            "size": len(p.bits),
            "receipt": p.receipt,
        }
        for ov, p in scored[:k]
    ]

def split_packet(packet: Packet, parts: int = 2) -> list[Packet]:
    """Split a packet into smaller packets that share the same count and receipt."""
    if parts < 2 or not packet.bits:
        return [packet]
    items = list(packet.bits)
    size = max(1, len(items) // parts)
    out = []
    for i in range(0, len(items), size):
        chunk = set(items[i:i + size])
        if chunk:
            out.append(Packet(chunk, packet.count, packet.label, packet.receipt))
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
            new_packets.append(Packet(bits, count, group[0].label, group[0].receipt))
            merged += len(group) - 1
        else:
            new_packets.append(p)
    if merged:
        _write(new_packets)
    return merged

def reinforce(label: str, amount: int = 1) -> int:
    """Increase the count of packets matching label. Returns new count or 0."""
    packets = load_packets()
    found = 0
    for p in packets:
        if p.label == label:
            p.count += amount
            found = p.count
    if found:
        _write(packets)
    return found

def accumulate(
    query_bits: set[int],
    success: bool,
    label: str = "",
    predicted: str = "public success",
    measured: str = "",
    context: dict[str, Any] | None = None,
) -> None:
    """Add or reinforce a packet from an outcome. Does not record SIM."""
    if not success:
        return
    receipt = {
        "predicted": predicted,
        "measured": measured or "public_correct",
        "context": context or {},
    }
    append_packet(Packet(query_bits, 1, label, receipt))
    merge_similar()
