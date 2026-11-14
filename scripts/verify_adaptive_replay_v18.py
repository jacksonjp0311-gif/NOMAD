"""Compare deterministic adaptive-study replay without importing any learner."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def deterministic_trial(row):
    return {key:row[key] for key in ('split','family','seed','mode','status','input_sha256',
        'trace','metrics','decisions','final_state_sha256')} | {'operation_counts':
        {key:value for key,value in row['telemetry'].items() if not key.endswith('_seconds')}}


def compare(plan_path,original_path,replay_path):
    plan=json.loads(plan_path.read_bytes());original=json.loads(original_path.read_bytes());replay=json.loads(replay_path.read_bytes())
    payload=plan['payload'];design=payload['design']
    if plan['sha256']!=digest(payload):raise ValueError('plan commitment changed')
    expected={(f,s,m) for f in design['families'] for s in design['evaluation_seeds'] for m in design['modes']}
    for name,identity in payload['source_sha256'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path)!=identity:raise ValueError('frozen implementation changed: '+name)
    indexed=[]
    for path,result in ((original_path,original),(replay_path,replay)):
        if (result.get('status')!='COMPLETED' or result.get('split')!='evaluation'
                or result.get('plan_sha256')!=plan['sha256'] or result.get('source_stable') is not True
                or result.get('config')!=design['controller_config']
                or result.get('source_sha256_before')!=payload['source_sha256']
                or result.get('source_sha256_after')!=payload['source_sha256']):
            raise ValueError('incomplete or differently registered run')
        started_path=path.with_name(path.stem+'.STARTED.json')
        started=json.loads(started_path.read_bytes())
        if (sha(started_path)!=result['started_receipt_sha256'] or started.get('evaluation_outcomes_generated') is not False
                or started.get('plan_sha256')!=plan['sha256'] or started.get('source_sha256')!=payload['source_sha256']):
            raise ValueError('pre-run commitment differs')
        index={}
        for row in result['trials']:
            key=(row['family'],row['seed'],row['mode'])
            receipt=row['process_receipt']
            if (key not in expected or key in index or row['status']!='COMPLETED'
                    or receipt.get('returncode')!=0 or receipt.get('timed_out') is not False
                    or receipt.get('truncated') is not False or receipt.get('cleanup')!='windows-job-empty-confirmed'
                    or len(row['trace'])!=design['steps']):raise ValueError('missing, duplicate or failed trial')
            index[key]=deterministic_trial(row)
        if set(index)!=expected:raise ValueError('incomplete registered trial inventory')
        indexed.append(index)
    for key in sorted(expected):
        if indexed[0][key]!=indexed[1][key]:raise ValueError('deterministic replay differs: '+str(key))
    return {'schema':'nomad.adaptive-replay-audit.v18','status':'PASS',
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':plan['sha256'],
        'original_sha256':sha(original_path),'replay_sha256':sha(replay_path),'verifier_sha256':sha(Path(__file__)),
        'trials_compared':len(expected),'forecasts_compared':len(expected)*design['steps'],
        'scored_forecasts_compared':len(expected)*(design['steps']-design['unscored_prefix']),
        'exact_trace_choice_input_finalstate_and_predictive_metrics_match':True,
        'operation_counts_match':True,'cost_fields_excluded':True,
        'scope':'same frozen streams replayed, no new independent seeds; primary run only for confirmatory cost claims',
        'coding_advantage':'NOT_ESTABLISHED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','original','replay','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();report=compare(args.plan,args.original,args.replay)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(report,handle,sort_keys=True,indent=2);handle.write('\n')
    print(json.dumps(report))


if __name__=='__main__':main()
