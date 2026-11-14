from __future__ import annotations

import argparse
import json

from .simulation import run_suite as run_v1
from .simulation_v2 import run_suite as run_v2
from .simulation_v3 import run_suite as run_v3
from .simulation_v4 import run_suite as run_v4
from .simulation_v5 import run_suite as run_v5
from .simulation_v6 import run_suite as run_v6
from .simulation_v7 import run_suite as run_v7
from .simulation_v8 import run_suite as run_v8
from .simulation_v9 import run_suite as run_v9
from .simulation_v10 import run_suite as run_v10
from .inquiry import make_inquiry_tasks, fit_inquiry, run_inquiry
from .genesis import evaluate_task
from .simulation_v10 import make_tasks


def main() -> None:
    parser = argparse.ArgumentParser(prog="nomad", description="NOMAD evidence-bounded transformation intelligence")
    parser.add_argument("--simulate", action="store_true", help="run current v0.10 GENESIS frozen study")
    parser.add_argument("--genesis-demo", action="store_true", help="physically repair a small Python repository and run tests")
    parser.add_argument("--simulate-v9", action="store_true", help="rerun preserved v0.9 INQUIRY study")
    parser.add_argument("--simulate-v8", action="store_true", help="rerun preserved v0.8 WORLD MODEL study")
    parser.add_argument("--inquiry-demo", action="store_true", help="run witnessed v0.9 diagnosis on a real on-disk synthetic repo")
    parser.add_argument("--simulate-v7", action="store_true", help="rerun preserved v0.7 CAUSAL SKILLS / CODEWORLD study")
    parser.add_argument("--simulate-v6", action="store_true", help="rerun preserved v0.6 WITNESS study")
    parser.add_argument("--simulate-v5", action="store_true", help="rerun preserved v0.5 ECHO MAP study")
    parser.add_argument("--simulate-v4", action="store_true", help="rerun preserved v0.4 MORPHIC study")
    parser.add_argument("--simulate-v3", action="store_true", help="rerun preserved v0.3 RESONANCE study")
    parser.add_argument("--simulate-v2", action="store_true", help="rerun preserved v0.2 study")
    parser.add_argument("--simulate-v1", action="store_true", help="rerun preserved v0.1 study")
    args = parser.parse_args()
    if args.simulate:
        print(json.dumps(run_v10(), indent=2))
    elif args.simulate_v9:
        print(json.dumps(run_v9(), indent=2))
    elif args.genesis_demo:
        task=make_tasks(17101,("sum_times_x_shift",),n_per_family=1)[0]
        result,receipt=evaluate_task(task,actual_tests=True)
        print(json.dumps({"version":"0.10.0","task_id":result.task_id,
            "synthesized":result.candidate,"candidate_vectors":result.candidate_evaluations,
            "public_unittest":result.public_tests,"witness_supported":result.witness_supported,
            "final_correct":result.final_correct,"receipt":receipt.receipt_hash if receipt else None},indent=2))
    elif args.simulate_v8:
        print(json.dumps(run_v8(), indent=2))
    elif args.inquiry_demo:
        training = make_inquiry_tasks(17, per_kind=3)
        model, likelihoods = fit_inquiry(training)
        fixture = make_inquiry_tasks(20017, per_kind=1)[0]
        result = run_inquiry(fixture, model, likelihoods, verify_repo_tests=True)
        print(json.dumps({
            "version": "0.9.0", "task_id": fixture.repo.task_id,
            "queries": [{"probe_id": r.probe_id, "passed": r.passed,
                         "cost": r.cost, "receipt": r.record_digest}
                        for r in result.probe_receipts],
            "candidate_attempts": result.candidate_attempts,
            "probe_cost_proxy": result.probe_cost,
            "witness_supported": result.witness_supported,
            "hidden_final_correct": result.final_correct,
        }, indent=2))
    elif args.simulate_v7:
        print(json.dumps(run_v7(), indent=2))
    elif args.simulate_v6:
        print(json.dumps(run_v6(), indent=2))
    elif args.simulate_v5:
        print(json.dumps(run_v5(), indent=2))
    elif args.simulate_v4:
        print(json.dumps(run_v4(), indent=2))
    elif args.simulate_v3:
        print(json.dumps(run_v3(), indent=2))
    elif args.simulate_v2:
        print(json.dumps(run_v2(), indent=2))
    elif args.simulate_v1:
        print(json.dumps(run_v1(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
