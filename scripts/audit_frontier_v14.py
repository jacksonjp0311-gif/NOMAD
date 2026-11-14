"""Fresh-process replay of selected FRONTIER patches against published package tests.

This independently re-runs executable outcomes; it is NOT external independent
research replication, and it cannot validate unexecuted search branches.
"""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.frontier import candidates,clone_frozen,digest,witness_and_record,verify_witness
from scripts.study_frontier_v14 import TASKS,prepare


def audit(path:Path|None=None)->dict:
    path=path or ROOT/'results/FRONTIER_STUDY_V014.json'
    study=json.loads(path.read_text())
    issues=[]; checked=0; observed_failures=0; contract_rejections=0
    task_by_id={t.id:t for t in TASKS}
    for section in ('training','cold','transferred'):
        for case in study[section]:
            task=task_by_id.get(case['id'])
            if not task or case['project']!=task.project:issues.append('task metadata mismatch');continue
            if not case['initial_public_failed']:issues.append('initial defect not observed: '+case['id'])
            if case['selected'] is None:
                if case['witness'].get('supported') or case['public_repaired']:
                    issues.append('unsupported success without candidate: '+case['id'])
                continue
            observed_failures+=1
            with tempfile.TemporaryDirectory(prefix='nomad-frontier-audit-') as td:
                repo,mutated=prepare(task,Path(td))
                prior=case['selected']
                options=[c for c in candidates(mutated,f'{task.project}/__init__.py',task.selector)
                         if c.line==prior['line'] and c.owner==prior['owner'] and c.family==prior['family']
                         and digest(c.render(mutated))==prior['candidate_sha256']]
                if len(options)!=1:issues.append('missing or ambiguous selected source patch: '+case['id']);continue
                c=options[0]
                exact=digest(c.render(mutated))==digest((ROOT/'external_sources'/task.project/task.project/'__init__.py').read_text())
                if exact != case['evaluator_exact_original_restoration']:
                    issues.append('evaluated exact restoration changed: '+case['id'])
                receipt=witness_and_record(repo,task.project,c,mutated)
                if not verify_witness(case['witness']):issues.append('saved receipt checksum invalid: '+case['id'])
                if (receipt.get('supported')!=case['witness'].get('supported') or
                    receipt.get('upstream_suite_passed')!=case['witness'].get('upstream_suite_passed') or
                    receipt.get('additional_contract',{}).get('status')!=case['witness'].get('additional_contract',{}).get('status')):
                    issues.append('fresh native replay disagrees: '+section+':'+case['id'])
                if receipt['additional_contract']['status']=='failed':contract_rejections+=1
                checked+=1
    # The defining negative example is mandatory in this release.
    negative=next((r for r in study['transferred'] if r['id']=='catalogue-names'),None)
    if not negative or negative['witness'].get('supported') or negative['witness'].get('additional_contract',{}).get('status')!='failed':
        issues.append('counterexample contract did not block overfit learned patch')
    return {'schema':'nomad.frontier.audit.v1','status':'passed' if not issues else 'failed',
            'selected_patches_replayed':checked,'selected_cases_present':observed_failures,
            'contract_rejections_observed':contract_rejections,
            'upstream_packages':sorted(set(t.project for t in TASKS)),
            'native_rust':'not tested — rustc not installed',
            'external_issue_research_gate':'HOLD','issues':issues}


def main():
    r=audit();print(json.dumps(r,indent=2));sys.exit(0 if r['status']=='passed' else 1)
if __name__=='__main__':main()
