"""Tests for logos suite."""
from logos.probe import encode
from logos.suite import load, run, twin


def test_load():
    suite = load()
    assert len(suite) == 8
    assert suite[0]["id"] == "ls_area"


def test_twin_causal():
    claim = {"id": "ls_area", "claim": ["area", "rows", "columns"]}
    bits = encode(claim["claim"])
    r = twin(claim, bits, set())
    assert r["causal"] is True
    assert r["field_score"] > r["cold_score"]


def test_twin_not_causal():
    claim = {"id": "ls_area", "claim": ["area", "rows", "columns"]}
    bits = encode(claim["claim"])
    r = twin(claim, bits, bits)
    assert r["causal"] is False


def test_run():
    suite = load()
    field = {c["id"]: encode(c["claim"]) for c in suite}
    cold = {c["id"]: set() for c in suite}
    result = run(field, cold)
    assert result["certified"] == 8
    assert result["total"] == 8
