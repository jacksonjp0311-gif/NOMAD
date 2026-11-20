"""Orbit algorithm.

Derived from the invariant that geometry follows relational statistics in the
data, not the model architecture (translation symmetry / collective pull).

Two packets are related when they share an operator outcome or when one
overlaps the other. A query pulls in packets that overlap the top direct hits
even if they do not overlap the query itself. This is the one-hop orbit.

No continuous embeddings. No Fourier basis. Integer overlap only.
"""
from __future__ import annotations

from typing import Any

from .weights import load_packets, Packet

def relate(a: Packet, b: Packet) -> int:
    """Relation score. Overlap plus shared operator from receipts."""
    score = a.overlap(b.bits)
    op_a = a.receipt.get("context", {}).get("operator") or a.receipt.get("context", {}).get("bias", {}).get("operator")
    op_b = b.receipt.get("context", {}).get("operator") or b.receipt.get("context", {}).get("bias", {}).get("operator")
    if op_a and op_a == op_b:
        score += 2
    return score

def orbit(query_bits: set[int], k: int = 8) -> list[dict[str, Any]]:
    """One-hop readout.

    Direct hits by overlap, then packets that relate to those hits.
    """
    packets = load_packets()
    direct = sorted(
        packets,
        key=lambda p: p.overlap(query_bits) * p.count,
        reverse=True,
    )[:k]
    seen = {id(p) for p in direct}
    expanded = list(direct)
    for hit in direct:
        for p in packets:
            if id(p) in seen:
                continue
            if relate(hit, p) > 0:
                expanded.append(p)
                seen.add(id(p))
                if len(expanded) >= k * 2:
                    break
        if len(expanded) >= k * 2:
            break
    out = []
    for p in expanded[:k]:
        out.append({
            "overlap": p.overlap(query_bits),
            "count": p.count,
            "label": p.label,
            "size": len(p.bits),
            "receipt": p.receipt,
            "orbit": True,
        })
    return out
