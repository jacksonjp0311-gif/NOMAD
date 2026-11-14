"""Retrospective v0.15 gated-prior replay on known external-source mutations.

All four tasks were seen during v0.14 development. NOT a new blind test.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.run_recursion_v15 import eligible_prior_study
from scripts.study_frontier_v14 import TASKS,case


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path)
    args=p.parse_args()
    history=json.loads((ROOT/'results/FRONTIER_STUDY_V014.json').read_text())
    prior_record,prior=eligible_prior_study(history)
    rows=[]
    for task in TASKS:
        if task.split!='release':continue
        rec,_=case(task,prior,budget=12,timeout_s=5.)
        rows.append({'id':task.id,'project':task.project,
            'public_repaired':rec['public_repaired'],
            'witnessed':rec['witness'].get('supported'),
            'attempts':rec['attempts'],
            'source_restored_exactly':rec['evaluator_exact_original_restoration'],
            'witness_valid':rec['witness_valid'],
            'additional_contract':rec['witness'].get('additional_contract',{}).get('status','not_applicable')})
    base={r['id']:r for r in history['cold']}
    result={'schema':'nomad.recursion.retrospective-native-replay.v1',
            'benchmark':'KNOWN v0.14 upstream-source mutations (not blind release cases)',
            'rows':rows,'accepted':sum(bool(x['witnessed']) for x in rows),
            'cold_v14_accepted':sum(bool(base[x['id']]['witness']['supported']) for x in rows),
            'same_attempt_counts_as_cold':all(x['attempts']==base[x['id']]['attempts'] for x in rows),
            'same_acceptance_as_cold':all(x['witnessed']==base[x['id']]['witness'].get('supported') for x in rows),
            'production_promotion':'HOLD; no demonstrated unseen external transfer'}
    if args.output:
        if args.output.exists():raise SystemExit('refusing overwrite')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
