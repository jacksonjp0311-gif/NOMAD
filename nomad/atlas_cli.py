"""Stable v0.11 public entrypoint; previous experimental CLIs are preserved."""
from __future__ import annotations
import argparse,json
from .causal_atlas import make_atlas_tasks,train_impact_model,SymbolGraph,observe_intervention,repair_atlas_task
from .simulation_v11 import INTERVENTION

def main():
    p=argparse.ArgumentParser(prog='nomad-atlas',description='NOMAD v0.11 verified multi-file consequence demo')
    p.add_argument('--demo',action='store_true',help='run one generated multi-file file-edit/test/WITNESS cycle')
    p.add_argument('--summary',action='store_true',help='show the existing frozen research result without rerunning it')
    a=p.parse_args()
    if a.demo:
        training=make_atlas_tasks(907,per_family=1)
        learner=train_impact_model(training)
        task=make_atlas_tasks(5513,per_family=1)[0]
        graph=SymbolGraph(task.files)
        observations=observe_intervention(task,INTERVENTION)
        forecasts=[{'contract':c.key,'prediction':learner.predict(graph.features(c,task.changed_file))[0],
                    'actual_changed':r.changed}
                   for c,r in zip(task.contracts,observations)]
        repair=repair_atlas_task(task,priority='graph',actual_tests=True)
        print(json.dumps({'version':'0.11.0','scope':'trusted generated Python fixtures',
                          'impact_forecasts':forecasts,'codeworld_repair':repair},indent=2))
        if not (repair['final_correct'] and repair['witness_supported']):raise SystemExit(1)
    elif a.summary:
        from pathlib import Path
        p=Path(__file__).resolve().parents[1]/'results/study-v011-release.json'
        result=json.loads(p.read_text())
        print(json.dumps({'version':'0.11.0','configuration':result['configuration'],
                'impact_metrics':result['impact_metrics'],
                'repairs':{k:{n:v for n,v in row.items() if n!='case_receipts'} for k,row in result['repairs'].items()}},indent=2))
    else:p.print_help()

if __name__=='__main__':main()
