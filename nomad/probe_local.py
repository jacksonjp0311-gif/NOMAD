"""Local probe runner. Does not take the lease. Does not write the field.

Loads the current field snapshot and runs cold vs field vs attended on the
held-out probes. When a probe returns none, a composition stage tries short
binary compositions of library trees that share the probe input type.
Causal only if a composition certifies and plain does not.

Results are local. The body remains the authority for any field write.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

from .attend import attend, is_causal, tree_bits, _bits_of
from .world import Invalid, consult
from .world import run as world_run
from .world_loop import load_world_prior, probe_heldout
from .world_tasks import HELDOUT


def _packet_bits(prior: Any) -> list[dict[str, Any]]:
    out = []
    if not prior or not getattr(prior, "library", None):
        return out
    lib = prior.library
    items = lib.items() if isinstance(lib, dict) else enumerate(lib)
    for name, tree in items:
        bits = tree_bits(tree) if tree else _bits_of(str(name))
        out.append({"bits": bits, "count": 1, "name": str(name), "tree": tree})
    return out


def _query_bits(name: str, task: Any) -> set[int]:
    bits = _bits_of(name)
    for inp in getattr(task, "inputs", []) or []:
        bits |= _bits_of(str(inp[1]) if isinstance(inp, (list, tuple)) else str(inp))
    for tok in re.findall(r"[a-z]+", name.lower()):
        bits |= _bits_of(tok)
    return bits


def _tree_certifies(task: Any, tree: list, library: dict | None = None) -> bool:
    try:
        vals = [world_run(tree, r, library) for r, _e in task.public]
    except (Invalid, Exception):
        return False
    goal = [e for _r, e in task.public]
    if vals != goal:
        return False
    receipt = consult(task, tree)
    return receipt is not None and receipt.supported


def _compose_stage(task: Any, packets: list[dict[str, Any]], max_try: int = 64) -> list | None:
    """Try short binary compositions of library trees."""
    trees = [p["tree"] for p in packets if p.get("tree")][:16]
    ops = ("concat", "sub", "add", "mul")
    count = 0
    for op, a, b in itertools.product(ops, trees, trees):
        if count >= max_try:
            break
        tree = [op, a, b]
        count += 1
        if _tree_certifies(task, tree):
            return tree
    return None


def run() -> dict[str, Any]:
    field = load_world_prior()
    packets = _packet_bits(field)
    base = probe_heldout(field=field, write=False)
    results = []
    for name, h in HELDOUT.items():
        row = base["probes"].get(name, {})
        plain = row.get("kind") == "certified_correctness" or row.get("field_beats_control")
        t = h["task"]
        qbits = _query_bits(name, t)
        att = attend(qbits, packets, k=8)
        attended_cert = False
        composed = None
        if not plain:
            scored = [(len(set(p.get("bits") or []) & qbits), p) for p in packets]
            scored.sort(key=lambda x: -x[0])
            for sc, p in scored[:8]:
                if sc > 0 and p.get("tree") and _tree_certifies(t, p["tree"], field.library):
                    attended_cert = True
                    break
            if not attended_cert:
                composed = _compose_stage(t, packets)
        results.append({
            "probe": name,
            "plain": plain,
            "attended_bits": len(att.get("bits") or []),
            "attended_k": att.get("k", 0),
            "attended_certifies": attended_cert,
            "composed": composed,
            "composed_certifies": composed is not None,
            "causal": is_causal(attended_cert or composed is not None, plain),
        })
    return {
        "status": "complete",
        "probes": results,
        "note": "Local measurement only. Body remains authority.",
    }


def main() -> int:
    result = run()
    Path("data").mkdir(exist_ok=True)
    Path("data/probe_local.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
