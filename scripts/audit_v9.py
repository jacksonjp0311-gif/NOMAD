"""Independent replay of public diagnostic outcomes and stored proxy accounting.

Does not use the learned inquiry planner. Recreates unedited source worlds and
executes only the probe IDs recorded by the frozen trial, verifying receipts.
"""
from __future__ import annotations
import json, math, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.inquiry import make_inquiry_tasks, run_probe, repo_snapshot
from nomad.repo_world import materialize


def audit()->dict[str,object]:
    report=json.loads((ROOT/'results/simulation-v009.json').read_text())
    seeds=tuple(report['eval_seeds'])
    cases=0; replayed=0; receipt_mismatches=[]; arithmetic_errors=[]; budget_errors=[]
    policy_costs={p:[] for p in report['policies']}
    for run in report['runs']:
        seed=run['seed']
        if seed not in seeds:raise ValueError('run seed outside frozen plan')
        fixtures=make_inquiry_tasks(seed+20_000,per_kind=4)
        lookup={f.repo.task_id:f for f in fixtures}
        # Reported outcomes are checked against independent public-contract
        # execution, without access to candidate repair patch results.
        for p,rows in run['paired'].items():
            for row in rows:
                task=lookup[row['task_id']]
                if row['probes']>3 or row['probe_cost']>0.90000001:
                    budget_errors.append(row['task_id'])
                if abs(row['total_proxy_cost']-(row['attempts']+row['probe_cost']))>1e-9:
                    arithmetic_errors.append(row['task_id'])
                policy_costs[p].append(row['total_proxy_cost'])
                if len(row['query_ids'])!=len(set(row['query_ids'])):
                    budget_errors.append(row['task_id']+':duplicate')
                if not row['query_ids']:
                    continue
                with tempfile.TemporaryDirectory(prefix='nomad-v9-audit-') as td:
                    root=Path(td);materialize(task.repo,root)
                    starting_digest=repo_snapshot(root,task.repo)
                    by_id={x.probe_id:x for x in task.contracts}
                    for i,probe_id in enumerate(row['query_ids']):
                        observed=run_probe(root,task.repo,by_id[probe_id])
                        replayed+=1
                        if (observed.record_digest!=row['receipt_digests'][i]
                                or observed.passed!=row['query_outcomes'][i]
                                or not observed.verify(starting_digest)):
                            receipt_mismatches.append((task.repo.task_id,p,probe_id))
                    if repo_snapshot(root,task.repo)!=starting_digest:
                        raise AssertionError('probe experiment mutated source')
        cases+=len(fixtures)
    means={p:sum(v)/len(v) for p,v in policy_costs.items()}
    reduction=(means['world']-means['active'])/means['world']
    if abs(reduction-report['comparisons']['proxy_cost_reduction_vs_world'])>1e-10:
        arithmetic_errors.append('reported comparison mismatch')
    # An independent baseline-cost audit checks the same sampled tasks only.
    status='passed' if not (receipt_mismatches or arithmetic_errors or budget_errors) and cases==64 else 'failed'
    return {
        'schema':'nomad.v0.9.independent-probe-replay.v1','status':status,
        'evaluation_repos':cases,'probe_receipts_replayed':replayed,
        'receipt_mismatches':receipt_mismatches,'proxy_arithmetic_errors':arithmetic_errors,
        'probe_budget_errors':budget_errors,'independent_policy_mean_cost':means,
        'independent_cost_reduction_vs_world':reduction,
        'scope':'Checks public diagnostic execution and receipt hashes only. Does not independently reimplement patch generation or prove generalization.'
    }


if __name__=='__main__':
    report=audit()
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['status']=='passed' else 2)
