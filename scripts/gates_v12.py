"""Pure read-only assessment of preregistered MNEMONIC result."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

def report(study_path:Path|None=None, plan_path:Path|None=None) -> dict:
    study=json.loads((study_path or ROOT/'results/study-v012.json').read_text())
    plan=json.loads((plan_path or ROOT/'experiments/PLAN_V012.json').read_text())
    c=study['configuration']; s=study['scores']; d=study['drift']
    checks={
      'source_seeds_predeclared':c['training_seeds']==plan['training_seeds'],
      'calibration_seed_predeclared':c['calibration_seeds']==plan['calibration_seeds'],
      'heldout_seeds_predeclared':c['heldout_seeds']==plan['release_heldout_seeds'],
      'source_calibration_heldout_disjoint':not (set(c['training_seeds'])&set(c['heldout_seeds']) or set(c['calibration_seeds'])&set(c['heldout_seeds'])),
      'cross_process_recall':c['memory_loaded_from_separate_process'] is True,
      'heldout_cases_count':c['heldout_repositories']==plan['heldout_repositories'] and s['warm']['total']==plan['heldout_repositories']*9,
      'no_false_warm_predictions':s['warm']['false_classified']==0,
      'uncertain_cases_abstained':s['warm']['abstained']==c['heldout_repositories'],
      'warmed_model_beats_graph_accuracy':s['warm']['correct_classified']>s['graph']['correct_classified'],
      'warmed_model_beats_shuffled_accuracy':s['warm']['correct_classified']>s['shuffled']['correct_classified'],
      'warmed_model_beats_pooled_accuracy':s['warm']['correct_classified']>s['pooled']['correct_classified'],
      'test_priority_improves':s['warm']['mean_top3_impacts']>s['graph']['mean_top3_impacts'] and s['warm']['mean_top3_impacts']>s['cold']['mean_top3_impacts'],
      'counterexample_forces_contested':d['prior_prediction']=='impact' and d['counterexample_changed'] is False and d['after_witness']['status']=='contested',
      'history_immutable':d['frozen_predecessor_unchanged'] is True,
      'expiry_abstains':d['expired']['status']=='expired',
      'action_scope_abstains':d['changed_action']['outcome']=='abstain',
      'no_promotion_authority':d['after_witness']['authority']=='prediction_only',
    }
    return {'schema':'nomad.mnemonic.release-gates.v1','status':'passed' if all(checks.values()) else 'failed',
            'passed':sum(checks.values()),'total':len(checks),'checks':checks}

if __name__=='__main__':
    r=report();print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='passed' else 1)
