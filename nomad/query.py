"""Field query.

Answers by reading the weight field. A question is hashed to bits.
Readout returns the strongest overlapping packets. The answer is the
receipt of the best domain or learned packet. No generation.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .weights import readout

BITS = 4096

def _hash_bits(text: str, density: int = 64) -> set[int]:
    h = hashlib.sha256(text.encode()).digest()
    bits = set()
    for i in range(density):
        idx = int.from_bytes(h[i % 32:(i % 32) + 4], "big") % BITS
        bits.add(idx)
    return bits

def query(question: str, k: int = 5) -> dict[str, Any]:
    """Answer a question from the field."""
    bits = _hash_bits(question)
    context = readout(bits, k=k)
    if not context:
        return {"question": question, "answer": None, "reason": "empty field"}
    # Prefer domain packets, then any with a receipt.
    domain = [c for c in context if c.get("label", "").startswith("domain:")]
    chosen = domain[0] if domain else context[0]
    receipt = chosen.get("receipt", {})
    return {
        "question": question,
        "answer": receipt.get("context", {}).get("domain") or chosen.get("label"),
        "operator": receipt.get("context", {}).get("operator"),
        "overlap": chosen.get("overlap"),
        "count": chosen.get("count"),
        "label": chosen.get("label"),
        "reason": "field readout",
    }
