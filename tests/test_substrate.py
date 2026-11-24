"""Tests for the connective substrate. Run without the body."""
from __future__ import annotations

import os

from nomad.substrate import CoActivation, decay_packets, inhibit_orbit


def test_decay():
    packets = [{"count": 100, "bits": [1, 2]}, {"count": 3, "bits": [3]}]
    out = decay_packets(packets, gamma=0.97)
    assert out[0]["count"] == 97
    assert out[1]["count"] == 2
    assert out[0]["dormant"] is False
    zero = decay_packets([{"count": 1}], gamma=0.5)
    assert zero[0]["count"] == 0
    assert zero[0]["dormant"] is True


def test_inhibit():
    orbit = [
        {"bits": [1, 2], "op": "Add", "count": 10},
        {"bits": [1, 3], "op": "Sub", "count": 5},
        {"bits": [4], "op": "Mult", "count": 8},
    ]
    out = inhibit_orbit(orbit)
    ops = [p["op"] for p in out]
    assert "Add" in ops
    assert "Mult" in ops
    assert "Sub" not in ops


def test_coact():
    c = CoActivation(window=4)
    c.observe(["abs", "sub"])
    c.observe(["abs", "min"])
    c.observe(["abs", "sub", "min"])
    m = c.matrix()
    assert m["abs"]["sub"] == 2
    assert m["abs"]["min"] == 2
    pred = c.predict("abs")
    assert "sub" in pred
    assert "min" in pred


def test_flags_off_by_default():
    os.environ.pop("NOMAD_PACKET_DECAY", None)
    os.environ.pop("NOMAD_ORBIT_INHIBIT", None)
    os.environ.pop("NOMAD_COACT", None)
    from nomad import substrate
    assert substrate.decay_enabled() is False
    assert substrate.inhibit_enabled() is False
    assert substrate.coact_enabled() is False
