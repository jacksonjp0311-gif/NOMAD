"""Development-only forced-schedule state-retention comparison, no policy claim."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.persistent import PersistentConfig, PersistentController, canonical, digest, source_identity


def trial(policy, observations):
    config=PersistentConfig(state_policy=policy,commitment=64,credit_horizon=64,
                            detector_enabled=False,delayed_credit=False)
    wall,cpu=time.perf_counter(),time.process_time()
    controller=PersistentController(config)
    forced=('frequency','temporal','native','frequency','temporal','native','frequency','native')
    trace=[]
    for t,(action,outcome) in enumerate(observations):
        if t%64==0: controller.decide(available_actions=(forced[t//64],))
        p=controller.predict(action)
        trace.append({'step':t,'p':p,'mechanism':controller.selected})
        controller.observe(action,outcome)
    telemetry=dict(controller.telemetry)
    return {'policy':policy,'config':asdict(config),'trace':trace,'telemetry':telemetry,
            'wall_seconds':time.perf_counter()-wall,'controller_cpu_seconds':time.process_time()-cpu,
            'scope':'trusted in-process sequential demonstration, no worker/startup cost or inferential speedup claim'}


def run():
    before=source_identity()
    rng=random.Random(18186003); observations=[]
    for t in range(512):
        action=rng.randrange(2); past=observations[t-3][0] if t>=3 else 0
        outcome=action^past^int(rng.random()<.08); observations.append((action,outcome))
    trials=[trial(policy,observations) for policy in ('selectivewarm','cold')]
    matched=trials[0]['trace']==trials[1]['trace']
    stable=before==source_identity()
    return {'schema':'nomad.temporal-retention-development.v18','status':'PASS' if matched and stable else 'FAIL',
            'source_sha256_before':before,'source_sha256_after':source_identity(),'source_stable':stable,
            'observed_at_utc':datetime.now(timezone.utc).isoformat(),'seed':18186003,
            'information_sha256':digest(observations),'steps':512,'forced_schedule':True,
            'identical_forecasts_and_selection':matched,'trials':trials,
            'limits':'development diagnostic only; same forced selection, no adaptive utility or held-out efficacy inference'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('preserve diagnostic result')
    result=run(); args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(result,handle,indent=2,sort_keys=True); handle.write('\n')
    print(json.dumps({'status':result['status'],'identical':result['identical_forecasts_and_selection'],
        'policies':[{k:t[k] for k in ('policy','wall_seconds','controller_cpu_seconds','telemetry')} for t in result['trials']]}))
    raise SystemExit(0 if result['status']=='PASS' else 3)
