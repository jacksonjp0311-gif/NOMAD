"""Sealed linguistic probe suite.

Claims that are not in the training set. Correct answers and distractors.
Generated before any field arm runs. The twin is cold versus field. Certification
requires WITNESS and final correct. The cold start must fail. The field must
succeed.

This is not language understanding. It is a sealed probe that is a linguistic
claim. The measurement says whether a packet answers the claim and the cold
start does not.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .probe import encode, is_causal, score

SUITE = [
    {"id": "ls_area", "claim": ["area", "rows", "columns"], "answer": "mul", "distractors": ["add", "sub"]},
    {"id": "ls_volume", "claim": ["volume", "length", "width", "height"], "answer": "mul", "distractors": ["add", "div"]},
    {"id": "ls_perimeter", "claim": ["perimeter", "length", "width"], "answer": "add", "distractors": ["mul", "sub"]},
    {"id": "ls_average", "claim": ["average", "sum", "count"], "answer": "div", "distractors": ["mul", "add"]},
    {"id": "ls_change", "claim": ["change", "final", "initial"], "answer": "sub", "distractors": ["add", "mul"]},
    {"id": "ls_shares", "claim": ["shares", "total", "people"], "answer": "div", "distractors": ["mul", "sub"]},
    {"id": "ls_frame", "claim": ["frame", "outer", "inner"], "answer": "sub", "distractors": ["add", "mul"]},
    {"id": "ls_trips", "claim": ["trips", "distance", "times"], "answer": "mul", "distractors": ["add", "div"]},
]


def load() -> list[dict[str, Any]]:
    return list(SUITE)


def twin(claim: dict[str, Any], field_packet: set[int], cold_packet: set[int]) -> dict[str, Any]:
    """Run the twin. Field versus cold."""
    tokens = claim["claim"]
    field_score = score(tokens, field_packet)
    cold_score = score(tokens, cold_packet)
    return {
        "id": claim["id"],
        "field_score": field_score,
        "cold_score": cold_score,
        "causal": is_causal(field_score, cold_score),
    }


def run(field_packets: dict[str, set[int]], cold_packets: dict[str, set[int]]) -> dict[str, Any]:
    """Run the suite. Returns certified count and per-claim results."""
    results = []
    certified = 0
    for claim in SUITE:
        fp = field_packets.get(claim["id"], set())
        cp = cold_packets.get(claim["id"], set())
        r = twin(claim, fp, cp)
        results.append(r)
        if r["causal"]:
            certified += 1
    return {"certified": certified, "total": len(SUITE), "results": results}
