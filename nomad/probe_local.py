"""Local probe runner. Does not take the lease. Does not write the field.

Loads the current field snapshot and runs cold vs field vs attended on the
held-out probes. The attended packet carries a tree. The tree is evaluated
on the probe task. Causal only if the attended tree certifies and plain does
not.

For wall probes, a short local synthesizer tries small programs built from
the probe-relevant operators. Results are local. The body remains the
authority for any field write.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

from .attend import attend, is_causal, tree_bits, _bits_of
from .world import Invalid, OPSETS, consult, run
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
        vals = [run(tree, r, library) for r, _e in task.public]
    except (Invalid, Exception):
        return False
    goal = [e for _r, e in task.public]
    if vals != goal:
        return False
    receipt = consult(task, tree)
    return receipt is not None and receipt.supported


def _short_synth(task: Any, ops: tuple[str, ...], max_depth: int = 3) -> list | None:
    """Try small programs from the given operators."""
    var = task.inputs[0][0]
    base = ["var", var]
    # depth 1: op(base)
    for op in ops:
        tree = [op, base]
        if _tree_certifies(task, tree):
            return tree
    # depth 2: op(op(base)) or op(base, base)
    for op1, op2 in itertools.product(ops, repeat=2):
        tree = [op1, [op2, base]]
        if _tree_certifies(task, tree):
            return tree
        tree = [op1, base, base]
        if _tree_certifies(task, tree):
            return tree
    # depth 3: op(op(base), op(base))
    for op1, op2, op3 in itertools.product(ops, repeat=3):
        tree = [op1, [op2, base], [op3, base]]
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
        synth = None
        if not plain:
            scored = [(len(set(p.get("bits") or []) & qbits), p) for p in packets]
            scored.sort(key=lambda x: -x[0])
            for sc, p in scored[:8]:
                if sc > 0 and p.get("tree") and _tree_certifies(t, p["tree"], field.library):
                    attended_cert = True
                    break
            # short synth from the relevant opset
            kind = t.inputs[0][1] if t.inputs else "int"
            ops = OPSETS.get(kind, ())
            synth = _short_synth(t, ops)
        results.append({
            "probe": name,
            "plain": plain,
            "attended_bits": len(att.get("bits") or []),
            "attended_k": att.get("k", 0),
            "attended_certifies": attended_cert,
            "synth": synth,
            "synth_certifies": synth is not None,
            "causal": is_causal(attended_cert or synth is not None, plain),
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
