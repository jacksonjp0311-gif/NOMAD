"""Packet composition.

Independent packets compose by set union. If two packets are certified on
different families, their bit sets can be unioned into a composed packet.
The composed packet is tested on a held-out probe that neither family
trained. If it certifies and neither alone does, the composition is causal.
If not, it is just overlap.

Inspired by the composition invariant from CSPD. Not the soft prompts. Not
the transformer. The rule that independent representations can stack without
joint retraining.
"""
from __future__ import annotations

from typing import Any


def compose(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Union two packets. Count is the max. Receipt is both."""
    bits = sorted(set(a.get("bits") or []) | set(b.get("bits") or []))
    count = max(int(a.get("count", 1)), int(b.get("count", 1)))
    return {
        "bits": bits,
        "count": count,
        "op": a.get("op") if a.get("op") == b.get("op") else None,
        "composed_from": [a.get("id"), b.get("id")],
        "note": "composed by set union",
    }


def is_causal(composed: dict[str, Any], probe_result: dict[str, Any], a_alone: bool, b_alone: bool) -> bool:
    """True if composed certifies and neither parent alone does."""
    return bool(probe_result.get("certified")) and not a_alone and not b_alone
