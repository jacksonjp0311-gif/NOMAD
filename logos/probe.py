"""LOGOS probe encoding.

A linguistic claim is a set of tokens. The packet is a set of bits. The score
is integer overlap. The prior is the lexicon counts from MEANING. The twin is
the same paired measurement. The gate is the same.
"""
from __future__ import annotations

import hashlib
from typing import Any

BITS = 4096


def encode(tokens: list[str]) -> set[int]:
    """Hash tokens into a bit set."""
    bits = set()
    for t in tokens:
        h = hashlib.sha256(t.encode()).digest()
        for i in range(4):
            idx = int.from_bytes(h[i * 4:(i + 1) * 4], "big") % BITS
            bits.add(idx)
    return bits


def overlap(a: set[int], b: set[int]) -> int:
    return len(a & b)


def score(claim: list[str], packet_bits: set[int]) -> int:
    return overlap(encode(claim), packet_bits)


def is_causal(field_score: int, cold_score: int, threshold: int = 2) -> bool:
    """True if field exceeds threshold and cold does not."""
    return field_score >= threshold and cold_score < threshold
