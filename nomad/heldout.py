"""Held-out comparison: cold start versus a WITNESS-trained field prior.

The frozen family is square_product, (x * x) * (y * y), with a matched
budget of 2000 candidate evaluations and 7 AST nodes. Those constants
were fixed before the comparison. A cold prior (default Add, Sub, Mult
order, witnessed=0) exhausts the budget. A prior trained only on
WITNESS-backed multiply tasks, never on the held-out rows, finds the
program inside the budget.

`compare_live` uses the continuous field's saved prior as it stands.
If that prior has no WITNESS-backed successes, it will not show an
advantage. That is an honest live reading, not a failure of the
mechanism.

Search and memory do not certify. Both arms are scored with WITNESS
and a final split after synthesis on public examples only.
"""
from __future__ import annotations

import json
from typing import Any

from .domain_tasks import (
    HELD_OUT_CHALLENGE,
    HELD_OUT_FINAL,
    HELD_OUT_ID,
    HELD_OUT_MAX_EVAL,
    HELD_OUT_MAX_NODES,
    HELD_OUT_PUBLIC,
    TRAIN_MULTIPLY,
)
from .genesis import GrammarPrior, SynthesisTask, evaluate_task, load_prior_file
from .paths import data_root


def _heldout_task() -> SynthesisTask:
    return SynthesisTask(
        task_id=f"heldout-{HELD_OUT_ID}",
        source="def solve(x, y):\n    return 0\n",
        public=HELD_OUT_PUBLIC,
        challenge=HELD_OUT_CHALLENGE,
        final=HELD_OUT_FINAL,
        hidden_family=HELD_OUT_ID,
    )


def _summary(evaluation, prior: GrammarPrior) -> dict[str, Any]:
    context = evaluation.learned_context
    return {
        "candidate": evaluation.candidate,
        "public_correct": evaluation.public_tests,
        "witness_supported": evaluation.witness_supported,
        "final_correct": evaluation.final_correct,
        "certified": bool(evaluation.witness_supported and evaluation.final_correct),
        "evaluations": evaluation.candidate_evaluations,
        "abstained": evaluation.abstained,
        "order": list(prior.order(context)),
        "witnessed": prior.witnessed,
        "context": context,
    }


def train_multiply_prior() -> GrammarPrior:
    """Build a field prior only from WITNESS-backed multiply training tasks."""
    prior = GrammarPrior()
    for spec in TRAIN_MULTIPLY:
        task = SynthesisTask(
            task_id=spec["task_id"],
            source="def solve(x, y):\n    return 0\n",
            public=spec["public"],
            challenge=spec["challenge"],
            final=spec["final"],
            hidden_family="multiply",
        )
        evaluated, receipt = evaluate_task(task, prior=prior)
        if evaluated.witness_supported and evaluated.final_correct and receipt is not None:
            prior.add_witnessed(evaluated.learned_context, evaluated.candidate or "", receipt)
    return prior


def _compare_with(field: GrammarPrior, *, field_source: str) -> dict[str, Any]:
    task = _heldout_task()
    cold = GrammarPrior()
    cold_eval, _ = evaluate_task(
        task, prior=cold, max_nodes=HELD_OUT_MAX_NODES, max_eval=HELD_OUT_MAX_EVAL,
    )
    field_eval, _ = evaluate_task(
        task, prior=field, max_nodes=HELD_OUT_MAX_NODES, max_eval=HELD_OUT_MAX_EVAL,
    )
    cold_row = _summary(cold_eval, cold)
    field_row = _summary(field_eval, field)
    certified_advantage = field_row["certified"] and not cold_row["certified"]
    cost_advantage = (
        field_row["certified"]
        and cold_row["certified"]
        and field_row["evaluations"] < cold_row["evaluations"]
    )
    return {
        "family": HELD_OUT_ID,
        "expression": "(x * x) * (y * y)",
        "max_nodes": HELD_OUT_MAX_NODES,
        "max_eval": HELD_OUT_MAX_EVAL,
        "field_source": field_source,
        "cold": cold_row,
        "field": field_row,
        "advantage": certified_advantage or cost_advantage,
        "advantage_kind": (
            "certified_correctness" if certified_advantage
            else "evaluations" if cost_advantage
            else "none"
        ),
        "note": (
            "Advantage is a matched-budget result on this frozen family only. "
            "It is not unrestricted coding and not a general learning claim."
        ),
    }


def compare_mechanism() -> dict[str, Any]:
    """Cold start versus a prior trained on frozen multiply tasks, not held-out rows."""
    return _compare_with(train_multiply_prior(), field_source="witnessed_multiply_training")


def compare_live() -> dict[str, Any]:
    """Cold start versus the continuous field prior as saved on disk."""
    path = data_root() / "continuous" / "prior.json"
    field = load_prior_file(path)
    return _compare_with(field, field_source=str(path) if path.exists() else "empty_live_prior")


def train_balanced_prior(gamma: float = 0.97) -> GrammarPrior:
    """Field from witnessed multiply (mathematics) and subtract (language) training only."""
    from .domain_tasks import TRAIN_SUBTRACT
    prior = GrammarPrior()
    for family, specs in (("mathematics", TRAIN_MULTIPLY), ("language", TRAIN_SUBTRACT)):
        for spec in specs:
            task = SynthesisTask(
                task_id=spec["task_id"], source="def solve(x, y):\n    return 0\n",
                public=spec["public"], challenge=spec["challenge"], final=spec["final"],
                hidden_family=family,
            )
            evaluated, receipt = evaluate_task(task, prior=prior, family=family)
            if evaluated.witness_supported and evaluated.final_correct and receipt is not None:
                prior.add_witnessed(evaluated.learned_context, evaluated.candidate or "", receipt, family=family)
                prior.decay(gamma)
    return prior


def balance_report(field: GrammarPrior | None = None) -> dict[str, Any]:
    """Per-domain cold vs field cost, plus the held-out family, under the balanced field.

    Pass bar: held-out square_product stays won, and no domain needs more
    evaluations under the field than under the cold control.
    """
    from .domain_tasks import DOMAIN_OPERATORS, splits_for
    field = field or train_balanced_prior()
    cold = GrammarPrior()
    domains = {}
    regressions = []
    for domain in DOMAIN_OPERATORS:
        sp = splits_for(domain)
        task = SynthesisTask(
            task_id=f"balance-{domain}", source="def solve(x, y):\n    return 0\n",
            public=sp["public"], challenge=sp["challenge"], final=sp["final"], hidden_family=domain,
        )
        c, _ = evaluate_task(task, prior=cold)
        f, _ = evaluate_task(task, prior=field, family=domain)
        row = {
            "operator": sp["operator"],
            "cold": {"certified": bool(c.witness_supported and c.final_correct), "evaluations": c.candidate_evaluations},
            "field": {"certified": bool(f.witness_supported and f.final_correct), "evaluations": f.candidate_evaluations},
        }
        row["evaluations_saved"] = row["cold"]["evaluations"] - row["field"]["evaluations"]
        if (row["cold"]["certified"] and not row["field"]["certified"]) or row["evaluations_saved"] < 0:
            regressions.append(domain)
        domains[domain] = row
    held = _compare_with(field, field_source="balanced_training")
    return {
        "heldout": {"family": held["family"], "field_certified": held["field"]["certified"],
                    "cold_certified": held["cold"]["certified"], "advantage_kind": held["advantage_kind"]},
        "domains": domains,
        "regressions": regressions,
        "pass": bool(held["field"]["certified"] and not held["cold"]["certified"] and not regressions),
        "note": "Matched budget, frozen rows. Domain names label small integer families.",
    }


def compare(domain: str = "mathematics") -> dict[str, Any]:
    """Default entry: the frozen held-out mechanism comparison.

    `domain` is accepted for compatibility and ignored. The held-out family
    is square_product, not a domain stand-in.
    """
    del domain
    return compare_mechanism()


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="NOMAD held-out cold vs field comparison")
    parser.add_argument("mode", nargs="?", choices=("mechanism", "live", "balance"), default="mechanism")
    args = parser.parse_args(argv)
    if args.mode == "balance":
        result = balance_report()
    else:
        result = compare_live() if args.mode == "live" else compare_mechanism()
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
