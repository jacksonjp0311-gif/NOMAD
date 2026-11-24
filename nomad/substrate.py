"""Connective substrate. Integer dynamics on the field.

Three operations. Each is behind a flag. Each is measurable without the body.

1. Packet decay. Multiplicative integer decay on sleep. Old evidence fades
   unless re-earned. Flag: NOMAD_PACKET_DECAY.
2. Orbit inhibition. When two orbit packets share bits but disagree on
   operator, keep the higher-count packet. Flag: NOMAD_ORBIT_INHIBIT.
3. Co-activation window. Record which primitives are used together in
   certified outcomes. Flag: NOMAD_COACT.

None of these certify. WITNESS remains the gate. The substrate is the
temporal connective tissue. Interlink reads it.
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any


def decay_enabled() -> bool:
    return os.environ.get("NOMAD_PACKET_DECAY", "off").lower() == "on"


def inhibit_enabled() -> bool:
    return os.environ.get("NOMAD_ORBIT_INHIBIT", "off").lower() == "on"


def coact_enabled() -> bool:
    return os.environ.get("NOMAD_COACT", "off").lower() == "on"


def decay_packets(packets: list[dict[str, Any]], gamma: float = 0.97) -> list[dict[str, Any]]:
    """Apply integer decay. c <- floor(c * gamma). Zero is dormant, not deleted."""
    if not 0.0 < gamma <= 1.0:
        raise ValueError("gamma must be in (0, 1]")
    out = []
    for p in packets:
        c = int(p.get("count", 1))
        new_c = int(c * gamma)
        q = dict(p)
        q["count"] = max(0, new_c)
        q["dormant"] = q["count"] == 0
        out.append(q)
    return out


def inhibit_orbit(orbit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Suppress lower-count packets that share bits but disagree on operator."""
    if not orbit:
        return orbit
    kept = []
    for p in orbit:
        conflict = False
        for q in kept:
            if _shares_bits(p, q) and _op(p) != _op(q) and int(p.get("count", 0)) <= int(q.get("count", 0)):
                conflict = True
                break
        if not conflict:
            kept.append(p)
    return kept


def _shares_bits(p: dict[str, Any], q: dict[str, Any]) -> bool:
    sp = set(p.get("bits") or [])
    sq = set(q.get("bits") or [])
    return bool(sp & sq)


def _op(p: dict[str, Any]) -> str:
    return str(p.get("op") or p.get("operator") or "")


class CoActivation:
    """Sliding window of co-activated primitives."""

    def __init__(self, window: int = 16) -> None:
        self.window = window
        self.history: list[list[str]] = []

    def observe(self, primitives: list[str]) -> None:
        self.history.append(list(primitives))
        if len(self.history) > self.window:
            self.history = self.history[-self.window:]

    def matrix(self) -> dict[str, dict[str, int]]:
        pairs: Counter[tuple[str, str]] = Counter()
        for group in self.history:
            uniq = sorted(set(group))
            for i, a in enumerate(uniq):
                for b in uniq[i + 1:]:
                    pairs[(a, b)] += 1
        out: dict[str, dict[str, int]] = {}
        for (a, b), n in pairs.items():
            out.setdefault(a, {})[b] = n
            out.setdefault(b, {})[a] = n
        return out

    def predict(self, primitive: str) -> list[str]:
        """Return primitives that co-activate with the given one, by frequency."""
        m = self.matrix()
        return sorted(m.get(primitive, {}).keys(), key=lambda x: -m[primitive][x])
