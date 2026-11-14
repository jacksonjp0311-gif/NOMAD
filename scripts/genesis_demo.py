"""One on-disk Python-repository edit, tests, independent WITNESS, final split."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.genesis import evaluate_task
from nomad.simulation_v10 import make_tasks
results=[]
for t in make_tasks(17101,('difference_product','sum_times_x_shift','bilinear_plus','shifted_product'),n_per_family=2):
    ev,receipt=evaluate_task(t,actual_tests=True)
    results.append({'task_id':ev.task_id,'public_unittest':ev.public_tests,
                    'challenge':ev.witness_supported,'final':ev.final_correct,
                    'syntax':ev.candidate,'witness_receipt':receipt.receipt_hash if receipt else None})
print(json.dumps({'version':'0.10.0','integration_repositories':len(results),
                  'passed':sum(r['public_unittest'] and r['challenge'] and r['final'] for r in results),
                  'results':results},indent=2))
if not all(r['public_unittest'] and r['challenge'] and r['final'] for r in results):raise SystemExit(1)
