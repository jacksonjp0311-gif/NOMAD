"""Measurement only: leave-one-family-out cost of cold vs library search at each
max_size, for each training family, plus absdiff (held-out; reported, never used
to choose parameters). Changes no state. Run: python3 scripts/lofo_stage_probe.py
Columns per size: (size, cold evals, cold found, library evals, library found).
"""
import sys; sys.path.insert(0,'tests'); sys.path.insert(0,'.')  # run from repo root
from test_world import _train
from nomad.world import *
from nomad.world import _drive,_search_gen
from nomad.world_tasks import all_training, HELDOUT
ts=all_training()
def row(t,lib,mx=20000):
    out=[]
    for s in (3,4,5,6,7):
        c=_drive(_search_gen(t,tuple(OPSETS[t.opset]),{},s,mx))
        l=_drive(_search_gen(t,tuple(OPSETS[t.opset]),lib,s,mx))
        out.append((s,c.evaluations,c.tree is not None,l.evaluations,l.tree is not None))
    return out
for t in ts:
    p=_train({x.family for x in ts if x.family!=t.family})
    print(t.family,row(t,p.primitives_for(t.inputs)))
p=_train()
print("absdiff",row(HELDOUT["absdiff"]["task"],p.primitives_for(HELDOUT["absdiff"]["task"].inputs)))
print({n:render(v) for n,v in p.primitives_for(HELDOUT["absdiff"]["task"].inputs).items()})
