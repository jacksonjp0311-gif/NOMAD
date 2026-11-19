"""Bitwork cognition.

Routes and decides using the weight packets as the only memory.
No transformers. No floating-point nets. Integer overlap is the attention.
"""
from __future__ import annotations

from typing import Any

from .weights import Packet, load_packets, readout, accumulate

def attend(query_bits: set[int], k: int = 8) -> list[dict[str, Any]]:
    """Fixed attention. Top-k packets by integer overlap."""
    return readout(query_bits, k=k)

def decide(query_bits: set[int], options: list[str]) -> dict[str, Any]:
    """Choose among options by total overlap of their packets."""
    scores = {}
    for opt in options:
        # Simple: hash the option and measure overlap with the field
        from .continuous import _hash_bits
        opt_bits = _hash_bits(opt)
        hits = attend(opt_bits)
        scores[opt] = sum(h["overlap"] for h in hits)
    if not scores:
        return {"choice": None, "scores": {}, "receipt": "empty"}
    choice = max(scores, key=scores.get)
    return {
        "choice": choice,
        "scores": scores,
        "receipt": "exact",
    }

def learn(query_bits: set[int], success: bool, label: str = "") -> None:
    """Reinforce the field on success."""
    accumulate(query_bits, success, label=label)

def cycle(query: str, options: list[str] | None = None) -> dict[str, Any]:
    """One cognition cycle: attend, decide, return receipt."""
    from .continuous import _hash_bits
    qbits = _hash_bits(query)
    attention = attend(qbits)
    decision = decide(qbits, options or ["keep", "reject"])
    return {
        "query": query,
        "attention": attention,
        "decision": decision,
    }
