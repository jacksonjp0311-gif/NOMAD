"""Tests for logos probe."""
from logos.probe import encode, score, is_causal
from nomad.compose import compose


def test_encode():
    bits = encode(["area", "rows", "columns"])
    assert len(bits) == 12


def test_score():
    claim = ["area", "rows"]
    bits = encode(claim)
    assert score(claim, bits) == 8


def test_causal():
    assert is_causal(3, 1) is True
    assert is_causal(1, 1) is False
    assert is_causal(3, 3) is False


def test_compose_score():
    claim = ["area", "rows", "columns"]
    bits = list(encode(claim))
    a = {"id": "a", "bits": bits[:4], "count": 2, "op": None}
    b = {"id": "b", "bits": bits[4:8], "count": 3, "op": None}
    c = compose(a, b)
    assert score(claim, set(c["bits"])) == 8
