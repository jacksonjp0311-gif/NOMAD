"""Separate prospective adaptive arm E; preserves the frozen A/B/C/D protocol.

This version can seal a design and audit prerequisites. Its native experiment
dispatcher remains refused until complete mission resource limits are qualified.
It never opens private contracts, executes repositories, or claims transfer.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.adaptive import AdaptiveConfig
from scripts import experiment_frontier_v18 as original
from scripts import experiment_qualification_v18 as shared

SCHEMA='nomad.adaptive-repository-extension.v18'
FROZEN_ORIGINAL=ROOT/'experiments/PROTOCOL_FRONTIER_REPOSITORY_RECHECK_V018.json'
CORPUS=ROOT/'experiments/development/adaptive_sources/CORPUS.json'


def exposed_repositories():
    catalog=shared.read_json(CORPUS)
    return set(catalog['excluded_evaluation_repositories'])|set(catalog['additional_metadata_exposure_repositories'])


def whole_mission_cost_contract():
    return {'qualified':False,'total_cpu_available':False,'strict_peak_available':False,
        'required_coverage':['controller','predictor initialization and catch-up','candidate generation',
            'diagnostic probes','every Docker worker including test subprocesses','memory retrieval and cloning',
            'verification','interrupted/discarded attempts','recovery and cleanup'],
        'current_measurements':['controller process CPU','end-to-end trial wall time',
            'Windows supervisor Job CPU and native high-water counters'],
        'missing':['Linux daemon-owned worker CPU retained after container exit',
            'all-container and controller aggregate hard CPU/wall enforcement',
            'strict successful-memory-commit peak semantics','attributable backend/VM overhead'],
        'accounting':'Sum disjoint controller/host-supervisor/Linux-cgroup CPU scopes, excluding duplicate nested counters; wall is one encompassing interval.',
        'memory':'Record each enforced memory domain and native counter semantics separately. Never sum independent peaks and label it a simultaneous measured peak.',
        'numeric_aggregate_budget_registration':'HOLD pending measured native accounting and enforceable scope; per-worker and search ceilings inherit original protocol.'}


def protocol():
    frozen=shared.read_json(FROZEN_ORIGINAL)
    base=original.protocol()
    if frozen['payload']['protocol']!=base:raise ValueError('original four-arm protocol changed')
    config=AdaptiveConfig();config.validate()
    return {'schema':SCHEMA+'.protocol','original_A_to_D_protocol':base,
        'original_frozen_document_sha256':shared.file_hash(FROZEN_ORIGINAL),
        'additional_arm':{'label':'E','inherits':'D verified full pipeline',
            'controller_api':'initialize_functions(computation_controller=AdaptiveConfig or exact config dict)',
            'controller_config':asdict(config),'controller_input':'past verified public observations and public structural counts only',
            'quality_authority':'unchanged WITNESS plus independent final verification',
            'allocation':'frequency <=16 candidates/1 probe/0 GENESIS evaluations; temporal <=32/2/1024; native <=64/3/4096; abstain0',
            'ceilings':dict(original.BOUNDS),'cost_calibration_scope':'development prior; native coding-cost calibration not established'},
        'whole_mission_cost':whole_mission_cost_contract(),
        'prospective_additional_contrasts':{'primary':'E versus D independently accepted repair rate and total measured mission CPU',
            'quality_noninferiority_margin':0.02,'unit':'upstream repository; seed repeats are not independent units',
            'acceptance':'No efficiency claim unless lower one-sided95percent repository-level quality-difference bound >= -0.02 and Holm-corrected paired cost comparison favors E; estimator must be registered in a subsequent executable plan before private access.',
            'status':'DESIGN_ONLY_NOT_A_REGISTERED_EXECUTABLE_TEST'},
        'newly_exposed_evaluation_exclusions':sorted(exposed_repositories()),
        'evaluation_updates':False,'private_contracts_opened':False,
        'matching':'Original A-D arm definitions/statistics remain exact. E may allocate less work and thus a different bounded inventory; compare source/public/training evidence and qualified hard total budgets, report inventory differences.',
        'unimplemented_execution_gate':'New E schedule/cost estimator and aggregate resource receipt must be registered and qualified before dispatch.'}


def code_identity():
    return {**original.code_identity(),
        'scripts/experiment_repository_adaptive_v18.py':shared.file_hash(Path(__file__)),
        'experiments/development/adaptive_sources/CORPUS.json':shared.file_hash(CORPUS)}


def audit(corpus,root,*,inspect_public=True):
    for task in corpus.get('tasks',[]):
        if task.get('split')=='evaluation' and shared._repository(task['repository']) in exposed_repositories():
            raise ValueError('newly exposed adaptive-development repository cannot be unseen evaluation')
    return original.audit(corpus,root,inspect_public=inspect_public)


def cost_coverage(events,*,controller_cpu_seconds,wall_seconds):
    for value in (controller_cpu_seconds,wall_seconds):
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('finite observed costs required')
    names=[row['data']['container_name'] for row in events if row['kind']=='F_DISPATCHED']
    observations=[row['data']['execution'] for row in events if row['kind']=='F_OBSERVED']
    measured=[]; measured_names=[]
    for receipt in observations:
        metrics=receipt.get('supervisor_metrics')
        if isinstance(metrics,dict) and metrics.get('available') is True and all(
                type(metrics.get(k)) in (int,float) and math.isfinite(metrics[k]) and metrics[k]>=0
                for k in ('cpu_user_s','cpu_kernel_s')):
            measured.append(metrics); measured_names.append(receipt.get('container_name'))
    return {'schema':SCHEMA+'.cost-coverage','controller_cpu_seconds':controller_cpu_seconds,
        'wall_seconds':wall_seconds,'host_cli_supervisor_cpu_seconds':sum(m['cpu_user_s']+m['cpu_kernel_s'] for m in measured),
        'host_cli_cpu_coverage_complete':len(names)==len(set(names)) and len(measured_names)==len(names)
            and set(measured_names)==set(names),
        'dispatched_attempts':len(names),'host_supervisor_receipts':len(measured),
        'docker_worker_cpu_seconds':None,'total_mission_cpu_seconds':None,
        'strict_mission_peak_memory_bytes':None,'total_cost_qualification':'HOLD',
        'reason':'Docker CLI/Job counters do not include daemon-owned Linux workers; missing, interrupted or recovered attempts cannot be treated as free.'}


def freeze_design(output):
    payload={'schema':SCHEMA+'.design-only','protocol':protocol(),'source_sha256':code_identity(),
        'tasks_registered':0,'private_contracts_opened':False,
        'status':'AWAITING_NATIVE_COST_QUALIFICATION_AND_INDEPENDENT_CURATED_CORPUS'}
    document={'payload':payload,'sha256':shared.digest(payload)}
    shared.write_new(output,document);return document


def validate_design(document):
    payload=document.get('payload')
    if (not isinstance(payload,dict) or document.get('sha256')!=shared.digest(payload)
            or payload.get('schema')!=SCHEMA+'.design-only' or payload.get('protocol')!=protocol()
            or payload.get('source_sha256')!=code_identity()):raise ValueError('adaptive extension design/source changed')
    return payload


def refusal(document,output):
    reasons=[]
    if document is None:reasons.append('source-bound adaptive extension design absent')
    else:
        try:validate_design(document)
        except (ValueError,KeyError,TypeError,OSError) as error:reasons.append(str(error))
    reasons.extend(['qualified native13-probe containment and21-case function recovery required',
        'complete aggregate mission cost accounting and hard budgets are unqualified',
        'independent unseen repository corpus and executable E schedule/statistics not registered'])
    report={'schema':SCHEMA+'.run','status':'HOLD','execution':'NOT_RUN','reasons':reasons,
        'design_sha256':document.get('sha256') if isinstance(document,dict) else None,
        'source_sha256':code_identity(),'trials':[],'private_contracts_opened':False,
        'repository_code_executed':False,'coding_advantage':'NOT_ESTABLISHED',
        'cross_repository_transfer':'NOT_ESTABLISHED','cloud_calls':0}
    report['receipt_sha256']=shared.digest(report);shared.write_new(output,report);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    child=sub.add_parser('protocol');child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('run');child.add_argument('--design',type=Path);child.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=freeze_design(args.output) if args.action=='protocol' else refusal(shared.read_json(args.design) if args.design else None,args.output)
    print(json.dumps({'status':result.get('status',result.get('payload',{}).get('status')),'execution':result.get('execution')}))
    return 3 if result.get('status')=='HOLD' else 0


if __name__=='__main__':raise SystemExit(main())
