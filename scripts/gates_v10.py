"""Recompute GENESIS research gates from immutable study/audit/integration data.

This module performs calculations only. Gate labels do not authenticate the
report publisher; package consistency is handled by the release manifest.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def report():
    plan=json.loads((ROOT/'experiments/PLAN_V010.json').read_text())
    study=json.loads((ROOT/'results/study-v010.json').read_text())
    audit=json.loads((ROOT/'results/AUDIT_V010.json').read_text())
    on_disk=json.loads((ROOT/'results/GENESIS_CODEWORLD_INTEGRATION.json').read_text())
    prior=json.loads((ROOT/'results/GENESIS_PRIOR.json').read_text())
    modes=study['policies']
    c=modes['bitwork_context']['summary']
    g=modes['global']['summary']
    u=modes['enumerative']['summary']
    shifted=modes['shuffled_context']['summary']
    context_cost=c['mean_candidate_vectors']
    gates={
        'heldout_case_count':c['tasks']==plan['heldout_cases'],
        'old_fixed_v9_exhausted':c['v9_public_reachable']==plan['predeclared_pass_gates']['v9_fixed_success_on_public'],
        'witness_supported':c['witness_supported']>=plan['predeclared_pass_gates']['genesis_witness_supported_min'],
        'final_correct':c['final_correct']>=plan['predeclared_pass_gates']['genesis_final_correct_min'],
        'zero_false_witness':c['false_witness_support']<=plan['predeclared_pass_gates']['genesis_false_witness_support_max'],
        'context_better_than_global':context_cost<=g['mean_candidate_vectors'],
        'context_better_than_enumeration':context_cost<=u['mean_candidate_vectors'],
        'context_better_than_rotated_state':context_cost<shifted['mean_candidate_vectors'],
        'independent_numeric_audit':audit['status']=='passed' and audit['result_disagreements']==0 and audit['candidate_programs_recomputed']==4*c['tasks'],
        'original_training_records_witnessed':study['training']['verified_skills']==plan['training_cases'],
        'integrated_python_files':on_disk['passed']>=plan['predeclared_pass_gates']['on_disk_python_unittest_witness_final_min'],
        'persistent_prior_matches_trained_model':prior['prior']==study['learned_prior'] and hashlib.sha256(json.dumps(prior['prior'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==prior['sha256'],
    }
    return {'schema':'nomad.v0.10.release-gates.v1','version':'0.10.0',
            'status':'passed' if all(gates.values()) else 'failed',
            'gates':gates,
            'metrics':{'evaluation_tasks':c['tasks'],'final_correct':c['final_correct'],
                       'v9_fixed_correct':c['v9_public_reachable'],
                       'context_mean_evaluations':context_cost,
                       'global_mean_evaluations':g['mean_candidate_vectors'],
                       'enumeration_mean_evaluations':u['mean_candidate_vectors'],
                       'shifted_mean_evaluations':shifted['mean_candidate_vectors'],
                       'reduction_vs_enumeration_percent':100*(1-context_cost/u['mean_candidate_vectors']),
                       'reduction_vs_global_percent':100*(1-context_cost/g['mean_candidate_vectors']),
                       'verified_training_skills':study['training']['verified_skills'],
                       'on_disk_repos':on_disk['passed'],
                       'reference_checked_programs':audit['candidate_programs_recomputed']},
            'limitations':'Internal synthetic integer grammar, not an external benchmark or whole-process CPU estimate'}


if __name__=='__main__':
    print(json.dumps(report(),indent=2))
    if report()['status']!='passed':raise SystemExit(1)
