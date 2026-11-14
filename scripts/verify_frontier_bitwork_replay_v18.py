"""Independent trace arithmetic and fresh-process reproducibility audit."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(first, second):
    a,b=(json.loads(Path(path).read_bytes()) for path in (first,second))
    if a['status']!='COMPLETED' or b['status']!='COMPLETED' or a['plan_sha256']!=b['plan_sha256']:
        raise ValueError('completed same-plan executions required')
    if len(a['streams'])!=32 or len(b['streams'])!=32: raise ValueError('stream count changed')
    forecasts=scored=0
    for left,right in zip(a['streams'],b['streams']):
        for key in ('seed','family','input_sha256','trace','native_snapshot','model_snapshots'):
            if left[key]!=right[key]: raise ValueError('deterministic replay mismatch: '+key)
        for mode in left['metrics']:
            for key in ('mean_logloss','brier','forecasts','scored_forecasts'):
                if left['metrics'][mode][key]!=right['metrics'][mode][key]: raise ValueError('deterministic metric mismatch')
            count=left['metrics'][mode]['scored_forecasts']
            rows=left['trace'][-count:]
            ll=sum(-math.log(row['probabilities'][mode] if row['outcome'] else 1-row['probabilities'][mode]) for row in rows)/count
            bs=sum((row['probabilities'][mode]-row['outcome'])**2 for row in rows)/count
            if not math.isclose(ll,left['metrics'][mode]['mean_logloss'],rel_tol=0,abs_tol=1e-12): raise ValueError('log loss arithmetic mismatch')
            if not math.isclose(bs,left['metrics'][mode]['brier'],rel_tol=0,abs_tol=1e-12): raise ValueError('Brier arithmetic mismatch')
            forecasts+=len(left['trace']); scored+=count
    if a['assessment']['registered_contrasts']!=b['assessment']['registered_contrasts']:
        raise ValueError('registered analysis differs across replay')
    return {'schema':'nomad.frontier-bitwork-replay-audit.v18','status':'PASS',
        'original_result_sha256':sha(first),'replay_result_sha256':sha(second),'plan_sha256':a['plan_sha256'],
        'verifier_source_sha256':sha(__file__),'streams':32,'forecasts_compared':forecasts,
        'scored_forecasts_recomputed':scored,'exact_predictions_and_model_snapshots_match':True,
        'logloss_and_brier_independently_recomputed':True,
        'excluded_nondeterministic_fields':['wall_seconds','cpu_seconds','controller_cpu_seconds','peak_python_allocated_bytes_all_models'],
        'scope':'reproduction of already evaluated synthetic streams; not new independent efficacy samples',
        'coding_advantage':'NOT_ESTABLISHED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True); parser.add_argument('--replay',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    result=verify(args.original,args.replay)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle: json.dump(result,handle,sort_keys=True,indent=2); handle.write('\n')
    print(json.dumps(result))


if __name__=='__main__': main()
