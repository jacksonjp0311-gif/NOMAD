from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from nomad.inquiry import fit_inquiry, make_inquiry_tasks, run_inquiry
if __name__=='__main__':
    model, likelihoods=fit_inquiry(make_inquiry_tasks(17,per_kind=3))
    fixture=make_inquiry_tasks(20017,per_kind=1)[0]
    result=run_inquiry(fixture,model,likelihoods,policy='active',verify_repo_tests=True)
    print(json.dumps({
        'task_id': result.task_id,
        'probe_receipts':[{'probe_id':p.probe_id,'passed':p.passed,'cost':p.cost,'sha256':p.record_digest} for p in result.probe_receipts],
        'candidate_edits':result.candidate_attempts,'total_proxy_cost':result.total_proxy_cost,
        'witness_admitted':result.witness_supported,'withheld_final_correct':result.final_correct,
    },indent=2))
