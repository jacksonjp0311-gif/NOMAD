"""NOMAD MNEMONIC public CLI: inspect trusted-fixture witnessed memory."""
from __future__ import annotations
import argparse,json,tempfile
from pathlib import Path
from .mnemonic import EvidenceMemory
from .causal_atlas import SymbolGraph, make_atlas_tasks, observe_intervention
from .simulation_v12 import ACTION,fit_memory,tasks


def demo() -> dict:
    memory=fit_memory(tasks((17011,17047,17123,17183)))
    with tempfile.TemporaryDirectory(prefix='nomad-memory-demo-') as td:
        loc=Path(td)/'evidence.json';memory.save(loc)
        stored=EvidenceMemory.load(loc)
        task=make_atlas_tasks(29011)[0]
        graph=SymbolGraph(task.files)
        previews=[]
        for contract,receipt in zip(task.contracts,observe_intervention(task,ACTION)):
            pred=stored.recall(action_source=ACTION,features=graph.features(contract,task.changed_file),
                               now_epoch=0,target_task_id=task.task_id)
            previews.append({'contract':contract.key,'prediction':pred.outcome,
                             'support_tasks':pred.support_tasks,'authority':pred.authority,
                             'witness_observation':receipt.changed,'prediction_correct':
                                 pred.outcome=='abstain' or (pred.outcome=='impact')==receipt.changed})
        return {'version':'0.12.0','mode':'MNEMONIC remembered evidence across a save/load boundary',
                'memory_events':len(stored.events),'frozen':stored.frozen,
                'scope':'trusted generated fixtures, not arbitrary code',
                'predictions':previews,'current_witness_still_required':True}


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');args=p.parse_args()
    if not args.demo:p.error('Use --demo')
    print(json.dumps(demo(),indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
