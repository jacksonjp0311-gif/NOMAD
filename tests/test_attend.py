"""Tests for integer attention readout."""
from nomad.attend import attend, is_causal, overlap


def test_overlap():
    assert overlap({1, 2, 3}, {2, 3, 4}) == 2


def test_attend_union():
    packets = [
        {"bits": [1, 2, 3], "count": 2},
        {"bits": [3, 4], "count": 4},
        {"bits": [5], "count": 1},
    ]
    out = attend({1, 2}, packets, k=2)
    assert 1 in out["bits"]
    assert 2 in out["bits"]
    assert out["via"] == "attend:union"


def test_attend_none():
    packets = [{"bits": [10], "count": 1}]
    out = attend({1, 2}, packets)
    assert out["via"] == "attend:none"


def test_causal():
    assert is_causal(True, False) is True
    assert is_causal(True, True) is False
    assert is_causal(False, False) is False
