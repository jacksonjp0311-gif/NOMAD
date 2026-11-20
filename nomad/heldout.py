"""Held-out comparison.

Runs a domain task with an empty prior (cold start) and with the field
prior. Records candidates, correctness, evaluations, and operator order.
The difference is the field advantage in cost or correctness.
"""
from __future__ import annotations

import json
from typing import Any

from .genesis import SynthesisTask, synthesize, GrammarPrior
from .domain_tasks import examples_for
from .weights import load_packets

def compare(domain: str = "mathematics") -> dict[str, Any]:
    examples = examples_for(domain)
    task = SynthesisTask(
        task_id=f"heldout-{domain}",
        source="def solve(x, y):\n    return 0\n",
        public=examples,
        challenge=(),
        final=(),
    )
    cold = GrammarPrior()
    cold_result = synthesize(task, prior=cold)
    field = GrammarPrior()
    packets = load_packets()
    for p in packets:
        if p.label == f"domain:{domain}":
            op = p.receipt.get("context", {}).get("operator", "Add")
            field.operator.update(0, op, True)
            break
    field_result = synthesize(task, prior=field)
    return {
        "domain": domain,
        "cold": {
            "candidate": cold_result.candidate,
            "public_correct": cold_result.public_correct,
            "evaluations": cold_result.candidates_evaluated,
            "order": list(cold.order(0)),
        },
        "field": {
            "candidate": field_result.candidate,
            "public_correct": field_result.public_correct,
            "evaluations": field_result.candidates_evaluated,
            "order": list(field.order(0)),
        },
        "advantage": (
            field_result.public_correct and not cold_result.public_correct
        ) or (
            field_result.candidates_evaluated < cold_result.candidates_evaluated
        ),
    }

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", nargs="?", default="mathematics")
    args = parser.parse_args(argv)
    print(json.dumps(compare(args.domain), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
