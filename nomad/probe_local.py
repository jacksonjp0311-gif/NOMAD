"""Local probe runner. Does not take the lease. Does not write the field.

Loads the current field snapshot and runs cold vs field vs attended on the
held-out probes. Prints whether attention certifies where plain overlap does
not. Results are local. The body remains the authority for any field write.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .attend import attend, is_causal
from .world_loop import load_world_prior, probe_heldout
from .world_tasks import HELDOUT


def _packet_bits(prior: Any) -> list[dict[str, Any]]:
    """Extract packet-like entries from the prior library for attention."""
    out = []
    if not prior or not getattr(prior, "library", None):
        return out
    for p in prior.library:
        bits = []
        if isinstance(p, str):
            bits = [hash(p) % 4096]
        elif hasattr(p, "name"):
            bits = [hash(p.name) % 4096]
        out.append({"bits": bits, "count": 1, "name": str(p)})
    return out


def run() -> dict[str, Any]:
    field = load_world_prior()
    packets = _packet_bits(field)
    base = probe_heldout(field=field, write=False)
    results = []
    for name, h in HELDOUT.items():
        row = base["probes"].get(name, {})
        plain = row.get("kind") == "certified_correctness" or row.get("field_beats_control")
        # attended query is the probe name hashed to bits
        qbits = {hash(name) % 4096}
        att = attend(qbits, packets, k=4)
        # attended is a candidate; we only mark causal if plain did not certify
        attended_cert = bool(att.get("bits")) and not plain
        results.append({
            "probe": name,
            "plain": plain,
            "attended_bits": len(att.get("bits") or []),
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
