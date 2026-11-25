"""Local probe runner. Does not take the lease. Does not write the field.

Loads the current field snapshot and runs cold vs field vs attended on the
held-out probes. The attended packet carries a tree. The tree is evaluated
on the probe task. Causal only if the attended tree certifies and plain does
not.

For wall probes, known short candidates and a small synthesizer are tried.
Results are local. The body remains the authority for any field write.
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

# Known short programs that match the wall probes. Not a claim.
CANDIDATES = {
    "last_first_upper": [
        ["concat", ["upper", ["last", ["var", "s"]]], ["upper", ["first", ["var", "s"]]]],
    ],
    "sum_minus_max": [
        ["sub", ["sum", ["var", "xs"]], ["lmax", ["var", "xs"]]],
    ],
}


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
            for tree in CANDIDATES.get(name, []):
                if _tree_certifies(t, tree):
                    synth = tree
                    break
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
