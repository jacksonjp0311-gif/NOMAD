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

from .paths import data_root

BITS = 4096


def _packets_path() -> Path:
    return data_root() / "weights" / "packets.jsonl"

def _ensure() -> None:
    _packets_path().parent.mkdir(parents=True, exist_ok=True)

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
    with _packets_path().open("a") as f:
        f.write(json.dumps(packet.as_dict(), separators=(",", ":")) + "\n")

def load_packets() -> list[Packet]:
    if not _packets_path().exists():
        return []
    packets = []
    with _packets_path().open() as f:
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
    _packets_path().write_text("".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in packets))

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

def merge_list(packets: list[Packet], threshold: int = 32) -> tuple[list[Packet], int]:
    """merge_similar's rule on an in-memory list: (new list, number of merges). Pure."""
    if len(packets) < 2:
        return packets, 0
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
    return new_packets, merged


def merge_similar(threshold: int = 32) -> int:
    """Merge packets that share high overlap. Returns number of merges."""
    packets = load_packets()
    if len(packets) < 2:
        return 0
    new_packets, merged = merge_list(packets, threshold)
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


def accumulate_list(packets: list[Packet], query_bits: set[int], success: bool, label: str = "",
                    predicted: str = "public success", measured: str = "",
                    context: dict[str, Any] | None = None) -> list[Packet]:
    """accumulate() on an in-memory list (append, then merge_similar's rule); for the sleep learner's
    single atomic commit (docs/INTEGRITY.md). Same result as accumulate() on the file."""
    if not success:
        return packets
    receipt = {"predicted": predicted, "measured": measured or "public_correct", "context": context or {}}
    return merge_list(packets + [Packet(query_bits, 1, label, receipt)])[0]


def reinforce_list(packets: list[Packet], label: str, amount: int = 1) -> int:
    """reinforce() on an in-memory list. Returns new count or 0."""
    found = 0
    for p in packets:
        if p.label == label:
            p.count += amount
            found = p.count
    return found


def serialize(packets: list[Packet]) -> str:
    return "".join(json.dumps(p.as_dict(), separators=(",", ":")) + "\n" for p in packets)


def packets_path() -> Path:
    return _packets_path()
