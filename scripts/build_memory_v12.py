"""Capture witnessed training effects, freeze, save, and EXIT this interpreter.

The held-out study must run separately and must never call this during its
reporting step. Output paths are create-only.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v12 import fit_memory,tasks,TRAIN_SEEDS

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output)
    if not out.is_absolute():out=ROOT/out
    if out.exists():raise SystemExit('Refusing to overwrite existing evidence memory')
    memory=fit_memory(tasks(TRAIN_SEEDS))
    checksum=memory.save(out)
    print(json.dumps({'schema':'nomad.mnemonic.training-batch.v1',
       'training_seeds':TRAIN_SEEDS, 'events':len(memory.events),
       'frozen':memory.frozen, 'payload_sha256':checksum,
       'chain_head':memory.head, 'output':str(out)},indent=2))
