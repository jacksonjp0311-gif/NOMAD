"""Tests for packet composition."""
from nomad.compose import compose, is_causal


def test_compose():
    a = {"id": "a", "bits": [1, 2], "count": 5, "op": "Add"}
    b = {"id": "b", "bits": [2, 3], "count": 3, "op": "Add"}
    c = compose(a, b)
    assert c["bits"] == [1, 2, 3]
    assert c["count"] == 5
    assert c["op"] == "Add"
    assert c["composed_from"] == ["a", "b"]


def test_causal():
    assert is_causal({}, {"certified": True}, False, False) is True
    assert is_causal({}, {"certified": True}, True, False) is False
    assert is_causal({}, {"certified": False}, False, False) is False
