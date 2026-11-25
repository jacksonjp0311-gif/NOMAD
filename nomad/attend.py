"""Integer attention readout over the field.

A query is a bit set. Keys and values are packets already in the field.
Score is integer overlap. Weights start as the score itself (linear).
The attended output is the bit-set union of the top-k packets by score.

Trees are encoded by their operator nodes so attention can prefer packets
whose structure matches the probe type. It is only a learning measurement
if the attended packet certifies a held-out probe and the plain overlap does
not. The body remains the authority.
"""
from __future__ import annotations

import hashlib
from typing import Any


def _bits_of(text: str, n: int = 4) -> set[int]:
    h = hashlib.sha256(text.encode()).digest()
    return {int.from_bytes(h[i * 4:(i + 1) * 4], "big") % 4096 for i in range(n)}


def tree_bits(tree: Any) -> set[int]:
    """Encode a program tree by its operator nodes."""
    bits: set[int] = set()
    def walk(t):
        nonlocal bits
        if isinstance(t, list) and t:
            bits |= _bits_of(str(t[0]))
            for c in t[1:]:
                walk(c)
        elif isinstance(t, str):
            bits |= _bits_of(t)
    walk(tree)
    return bits


def overlap(a: set[int], b: set[int]) -> int:
    return len(a & b)


def attend(query: set[int], packets: list[dict[str, Any]], k: int = 4) -> dict[str, Any]:
    """Return an attended packet: union of top-k by integer overlap with query."""
    scored = []
    for p in packets:
        bits = set(p.get("bits") or [])
        sc = overlap(query, bits)
        scored.append((sc, p))
    scored.sort(key=lambda x: -x[0])
    top = [p for sc, p in scored[:k] if sc > 0]
    if not top:
        return {"bits": set(), "count": 0, "via": "attend:none"}
    union = set()
    total = 0
    for p in top:
        union |= set(p.get("bits") or [])
        total += int(p.get("count") or 0)
    return {
        "bits": union,
        "count": total // max(1, len(top)),
        "via": "attend:union",
        "k": len(top),
    }


def is_causal(attended_certifies: bool, plain_certifies: bool) -> bool:
    """True only if attention certifies and plain overlap does not."""
    return attended_certifies and not plain_certifies
