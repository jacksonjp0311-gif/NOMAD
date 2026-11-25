"""Local probe runner. Does not take the lease. Does not write the field.

Loads the current field snapshot and runs cold vs field vs attended on the
held-out probes. Prints whether attention certifies where plain overlap does
not. Results are local. The body remains the authority for any field write.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .attend import attend, is_causal, tree_bits, _bits_of
from .world_loop import load_world_prior, probe_heldout
from .world_tasks import HELDOUT


def _packet_bits(prior: Any) -> list[dict[str, Any]]:
    """Extract packet-like entries from the prior library for attention."""
    out = []
    if not prior or not getattr(prior, "library", None):
        return out
    lib = prior.library
    items = lib.items() if isinstance(lib, dict) else enumerate(lib)
    for name, tree in items:
        bits = tree_bits(tree) if tree else _bits_of(str(name))
        out.append({"bits": bits, "count": 1, "name": str(name)})
    return out


def run() -> dict[str, Any]:
    field = load_world_prior()
    packets = _packet_bits(field)
    base = probe_heldout(field=field, write=False)
    results = []
    for name, h in HELDOUT.items():
        row = base["probes"].get(name, {})
        plain = row.get("kind") == "certified_correctness" or row.get("field_beats_control")
        t = h["task"]
        qbits = _bits_of(name)
        for inp in getattr(t, "inputs", []) or []:
            qbits |= _bits_of(str(inp[1]) if isinstance(inp, (list, tuple)) else str(inp))
        att = attend(qbits, packets, k=8)
        attended_cert = bool(att.get("bits")) and not plain
        results.append({
            "probe": name,
            "plain": plain,
            "attended_bits": len(att.get("bits") or []),
            "attended_k": att.get("k", 0),
            "causal": is_causal(attended_cert, plain),
        })
    return {
        "status": "complete",
        "probes": results,
        "note": "Local measurement only. Does not write the field. Body remains authority.",
    }


def main() -> int:
    result = run()
    Path("data").mkdir(exist_ok=True)
    Path("data/probe_local.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
