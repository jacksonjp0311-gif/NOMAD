"""Read-only deterministic replay comparison; no predictor imports."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_bytes())


def deterministic(row):
    selected={key:row[key] for key in ('split','family','seed','mode','status','config',
        'input_sha256','trace','metrics','decisions','switches','detector_metrics',
        'final_state_sha256','source_stable')}
    selected['operation_counts']={k:v for k,v in row['telemetry'].items() if not k.endswith('_seconds')}
    selected['checkpoints']=[{k:c[k] for k in ('observed_prefix','deterministic_state_sha256','method')} for c in row['checkpoints']]
    return selected


def compare(plan_path, original_path, replay_path):
    plan,original,replay=map(read,(plan_path,original_path,replay_path))
    design=plan['payload']['design']
    expected={(f,s,m) for f in design['families'] for s in design['evaluation_seeds'] for m in design['modes']}
    def inventory(result):
        if (result.get('status')!='COMPLETED' or result.get('source_stable') is not True
                or result.get('plan_sha256')!=plan['sha256']
                or result.get('source_sha256_before')!=plan['payload']['source_sha256']
                or result.get('source_sha256_after')!=plan['payload']['source_sha256']):
            raise ValueError('incomplete or differently bound replay')
        rows={(r['family'],r['seed'],r['mode']):r for r in result['trials']}
        if len(result['trials'])!=len(expected) or set(rows)!=expected: raise ValueError('trial inventory differs')
        if any(r['status']!='COMPLETED' or len(r['trace'])!=design['steps'] for r in rows.values()):
            raise ValueError('incomplete worker trace')
        return rows
    left,right=inventory(original),inventory(replay)
    for key in sorted(expected):
        if deterministic(left[key])!=deterministic(right[key]): raise ValueError('deterministic replay differs: '+str(key))
    return {'schema':'nomad.temporal-replay.v18','status':'PASS','trials_checked':len(expected),
        'forecasts_checked':len(expected)*design['steps'],'plan_file_sha256':sha(plan_path),
        'original_sha256':sha(original_path),'replay_sha256':sha(replay_path),
        'checked':'all forecasts, inputs, decisions, metrics, deterministic states/checkpoints and operation counts',
        'excluded':'timing, raw storage hashes/lengths containing timing telemetry, resource counters and statistical CPU conclusions',
        'scope':'same registered seeds; no new independent samples or second confirmatory cost experiment'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','original','replay','output'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists(): raise FileExistsError('preserve replay receipt')
    result=compare(a.plan,a.original,a.replay)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(result,out,indent=2,sort_keys=True); out.write('\n')
    print(json.dumps(result))


if __name__=='__main__': main()
