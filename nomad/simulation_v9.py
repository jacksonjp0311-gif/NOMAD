"""Frozen synthetic active-diagnosis experiment, with equal offered probe budgets."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import argparse
from pathlib import Path
from dataclasses import asdict
from statistics import mean
from typing import Iterable

from .inquiry import InquiryResult, fit_inquiry, make_inquiry_tasks, run_inquiry, summarize_inquiry

POLICIES = ("world", "prior_only", "active", "random", "all", "shuffled")
FROZEN_EVAL_SEEDS = (101, 137, 181, 223)


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def run_seed(seed: int, *, per_kind: int=4,
             policies: Iterable[str] = POLICIES,
             integration: bool = False) -> dict[str, object]:
    training = make_inquiry_tasks(seed, per_kind=per_kind)
    evaluation = make_inquiry_tasks(seed+20_000, per_kind=per_kind)
    world, likelihoods = fit_inquiry(training)
    chosen = tuple(policies)
    summaries = {}
    paired = {}
    for policy in chosen:
        results = [run_inquiry(f, world, likelihoods, policy=policy, negative_control_seed=seed)
                   for f in evaluation]
        s = summarize_inquiry(results)
        s["correct_first_file"] = sum(
            r.predicted_file == f.repo.true_bug_file for r, f in zip(results, evaluation)
        )
        s["first_file_accuracy"] = s["correct_first_file"]/len(evaluation)
        s["probe_budget_violations"] = sum(r.probe_cost > 0.90000001 or r.probes > 3 for r in results)
        summaries[policy] = s
        paired[policy] = [
            {"task_id": f.repo.task_id, "attempts": r.candidate_attempts,
             "probe_cost": r.probe_cost, "total_proxy_cost": r.total_proxy_cost,
             "probes": r.probes, "correct": r.final_correct,
             "first_file_correct": r.predicted_file == f.repo.true_bug_file,
             "query_ids": [p.probe_id for p in r.probe_receipts],
             "query_outcomes": [p.passed for p in r.probe_receipts],
             "receipt_digests": [p.record_digest for p in r.probe_receipts],
             "query_information_gains_bits": [round(q.information_gain_bits,8) for q in r.query_decisions],
            } for f, r in zip(evaluation, results)
        ]
    integ = None
    if integration:
        # Separate integration: physical source files edited, on-disk unittest
        # invoked, then WITNESS-held challenge and hidden final used.
        examples=make_inquiry_tasks(seed+40_000,per_kind=1)
        results=[run_inquiry(f,world,likelihoods,policy="active",verify_repo_tests=True)
                 for f in examples]
        integ={"tasks":len(results),"final_correct":sum(r.final_correct for r in results),
               "witness_supported":sum(r.witness_supported for r in results),
               "real_unittest_required":True,
               "probe_budget_violations":sum(r.probe_cost>0.90000001 or r.probes>3 for r in results)}
    return {
        "seed":seed,
        "training_repos":len(training),"evaluation_repos":len(evaluation),
        "training_likelihoods":likelihoods.snapshot(),
        "world_model_training_observations":world.observations,
        "policies":summaries,"paired":paired,"integration":integ,
    }


def run_suite(seeds: tuple[int,...]=FROZEN_EVAL_SEEDS,
              *, per_kind: int=4,
              integration: bool = True,
              isolate: bool = True) -> dict[str, object]:
    if isolate:
        runs=[]
        for s in seeds:
            command=[sys.executable, "-m", "nomad.simulation_v9", "--seed", str(s),
                     "--per-kind", str(per_kind)]
            if integration and s==seeds[0]:
                command.append("--integration")
            p=subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True,
                             capture_output=True, timeout=120)
            if p.returncode:
                raise RuntimeError(f"isolated seed {s} failed: {p.stderr[-3000:]}")
            result=json.loads(p.stdout)
            if result["seed"]!=s:
                raise RuntimeError("seed subprocess returned inconsistent identity")
            runs.append(result)
    else:
        runs=[run_seed(s,per_kind=per_kind,integration=integration and s==seeds[0]) for s in seeds]
    return assemble_runs(runs,seeds)


def assemble_runs(runs: list[dict[str,object]], seeds: tuple[int,...]) -> dict[str,object]:
    """Pure, deterministic assembly of independently executed seed batches."""
    if [int(r["seed"]) for r in runs] != list(seeds):
        raise ValueError("seed order or identity mismatch")
    policies=tuple(runs[0]["policies"])
    totals={}
    for p in policies:
        s=[r["policies"][p] for r in runs]
        tasks=sum(int(r["tasks"]) for r in s)
        totals[p]={
            "tasks":tasks,
            "final_correct":sum(int(r["final_correct"]) for r in s),
            "witness_supported":sum(int(r["witness_supported"]) for r in s),
            "mean_candidate_attempts":sum(float(r["mean_candidate_attempts"])*int(r["tasks"]) for r in s)/tasks,
            "mean_probe_count":sum(float(r["mean_probe_count"])*int(r["tasks"]) for r in s)/tasks,
            "mean_probe_proxy_cost":sum(float(r["mean_probe_proxy_cost"])*int(r["tasks"]) for r in s)/tasks,
            "mean_total_proxy_cost":sum(float(r["mean_total_proxy_cost"])*int(r["tasks"]) for r in s)/tasks,
            "first_file_correct":sum(int(r["correct_first_file"]) for r in s),
            "probe_budget_violations":sum(int(r["probe_budget_violations"]) for r in s),
        }
        totals[p]["first_file_accuracy"]=totals[p]["first_file_correct"]/tasks
    active=totals["active"]
    comparisons={
        f"proxy_cost_reduction_vs_{other}":
        (totals[other]["mean_total_proxy_cost"]-active["mean_total_proxy_cost"])/totals[other]["mean_total_proxy_cost"]
        for other in policies if other!="active"
    }
    comparisons["candidate_reduction_vs_world"]=(totals["world"]["mean_candidate_attempts"]-active["mean_candidate_attempts"])/totals["world"]["mean_candidate_attempts"]
    integration_rows=[r["integration"] for r in runs if r["integration"] is not None]
    integration={"tasks":sum(r["tasks"] for r in integration_rows),
                 "final_correct":sum(r["final_correct"] for r in integration_rows),
                 "witness_supported":sum(r["witness_supported"] for r in integration_rows),
                 "real_unittest_required":True,
                 "budget_violations":sum(r["probe_budget_violations"] for r in integration_rows)}
    return {
        "schema":"nomad.v0.9.active-diagnosis-study.v1",
        "version":"0.9.0", "codename":"INQUIRY",
        "eval_seeds":list(seeds), "train_seed_rule":"train seed = eval seed; evaluation seed = train seed + 20000",
        "split":"same 4 generated fault families; shuffled filenames; separate training/evaluation tasks",
        "candidate_cost_unit":"one attempted code edit and public test evaluation = 1 proxy unit",
        "probe_cost_units":{"core":0.24,"config":0.20,"middle":0.34,"entry":0.50},
        "max_probe_cost_per_repo":0.90,"max_probes_per_repo":3,
        "policies":totals,"comparisons":comparisons,
        "integration":integration,
        "runs":runs,
        "claim_boundary":(
            "Synthetic six-file Python repositories with fixed role APIs, single faults, a supplied patch vocabulary, and PUBLIC module-level contract probes. "
            "Probes have predeclared abstract costs, not measured CPU or energy. Training uses WITNESS-supported repaired locations; no evaluation fault labels are available to the planner. "
            "The same generated scenario families are present across train/evaluation, so results do not establish transfer to arbitrary repositories or truly novel causal concepts. "
            "The probe author knows reference behavior and the tester executes source in process; unsafe external repos are not supported by this demo."
        ),
    }


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Isolated NOMAD v0.9 seed runner")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--per-kind", type=int, default=4)
    parser.add_argument("--integration", action="store_true")
    args=parser.parse_args()
    print(json.dumps(run_seed(args.seed,per_kind=args.per_kind,integration=args.integration),indent=2))
