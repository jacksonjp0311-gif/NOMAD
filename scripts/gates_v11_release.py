"""Read-only release gates, computed solely from stored experiment evidence."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

def report() -> dict:
    study=json.loads((ROOT/'results/study-v011-release.json').read_text())
    plan=json.loads((ROOT/'experiments/PLAN_V011_RELEASE.json').read_text())
    conf=study['configuration'];m=study['impact_metrics'];rep=study['repairs']
    changed=[r['changed'] for r in study['effect_records']]
    dynamic=[r for r in study['effect_records'] if r['features']==['uncertain']]
    expected_impact=m['learned_atlas'];direct=m['direct_call_graph'];shuffle=m['shuffled_evidence']
    gates={
        'seed_set_matches_predeclared': conf['training_seeds']==plan['training_seeds'] and conf['heldout_seeds']==plan['heldout_seeds'],
        'correct_heldout_sample_count':conf['heldout_worlds']==plan['heldout_repositories'] and conf['contract_samples']==len(study['effect_records'])==plan['heldout_repositories']*plan['holdout_contracts_per_repository'],
        'learned_no_false_impact_predictions':expected_impact['fn']==expected_impact['fp']==0,
        'learned_f1_exceeds_call_only':expected_impact['f1']>direct['f1'] and expected_impact['f1']>=plan['gates']['impact_f1_min'],
        'negative_control_worse':shuffle['f1']<expected_impact['f1'],
        'uncertain_dynamic_abstentions':len(dynamic)==plan['heldout_repositories'] and all(r['learned_prediction']=='abstain' for r in dynamic),
        'flat_and_graph_final_correct':all(r['final_correct']==plan['integration_cases'] and r['witness_supported']==plan['integration_cases'] for r in rep.values()),
        'same_synthesis_options':rep['flat']['solved']==rep['graph']['solved']==plan['integration_cases'],
        'graph_fewer_file_visits':rep['graph']['total_file_visits']<rep['flat']['total_file_visits'],
        'no_pre_release_metadata_in_features':all('m'+str(k) not in repr(r['features']) for r in study['effect_records'] for k in plan['heldout_seeds']),
    }
    return {'schema':'nomad.v011.gates.v1','status':'passed' if all(gates.values()) else 'failed',
            'passed':sum(gates.values()),'total':len(gates),'checks':gates}

if __name__=='__main__':print(json.dumps(report(),indent=2))
