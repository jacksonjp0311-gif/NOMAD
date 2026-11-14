"""Fresh-process replay for one held-out seed; stdout JSON, no writes."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v12 import ACTION,tasks
from nomad.causal_atlas import SymbolGraph,observe_intervention

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,required=True)
    args=parser.parse_args()
    rows=[]
    for t in tasks((args.seed,)):
        graph=SymbolGraph(t.files)
        for contract,rec in zip(t.contracts,observe_intervention(t,ACTION)):
            rows.append({'task_id':t.task_id, 'contract':contract.key,
                         'features':list(graph.features(contract,t.changed_file)),
                         'changed':rec.changed,'source_digest':rec.before_digest,
                         'observed_digest':rec.receipt_digest})
    print(json.dumps({'seed':args.seed,'rows':rows},sort_keys=True))
