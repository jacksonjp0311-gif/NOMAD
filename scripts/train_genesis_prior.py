"""Rebuild the frozen GENESIS prior from original training-only tasks."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.genesis import train_prior
from nomad.genesis_store import save_prior,load_prior
from nomad.simulation_v10 import make_tasks
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
if args.output.exists():raise SystemExit('Refuse to overwrite existing prior')
plan=json.loads((ROOT/'experiments/PLAN_V010.json').read_text())
tasks=[]
for seed in plan['training_seeds']:
    tasks+=make_tasks(seed,tuple(plan['training_families']),n_per_family=plan['cases_per_family_per_seed'])
prior,counts=train_prior(tasks,max_nodes=plan['max_ast_nodes'],max_eval=plan['max_candidate_vector_evaluations'])
original=json.loads((ROOT/'results/study-v010.json').read_text())['learned_prior']
if prior.snapshot()!=original:raise SystemExit('Rebuilt model does not match frozen study')
sha=save_prior(args.output,prior)
if load_prior(args.output).snapshot()!=original:raise SystemExit('Saved prior failed round trip')
print(json.dumps({'status':'passed','witness_verified_skills':counts['verified_skills'],
                  'prior_sha256':sha,'path':str(args.output)},indent=2))
