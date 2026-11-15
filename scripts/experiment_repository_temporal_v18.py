"""Separate prospective persistent arm F: design and fail-closed prerequisite receipt.

This does not dispatch repositories or open private contracts. Original A-D
and the optional adaptive E design are retained without changing their arms.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nomad.persistent import PersistentConfig
from scripts import experiment_repository_adaptive_v18 as adaptive
from scripts import experiment_qualification_v18 as shared

SCHEMA='nomad.persistent-repository-extension.v18'
MECHANISM_PLAN=ROOT/'experiments/PLAN_TEMPORAL_V018.json'


def protocol():
    document=shared.read_json(MECHANISM_PLAN);payload=document['payload']
    if document['sha256']!=shared.digest(payload) or payload['schema']!='nomad.temporal-ascension.v18.plan':
        raise ValueError('frozen mechanism plan differs')
    config=payload['design']['controller_config'];PersistentConfig(**config).validate()
    for name,checksum in payload['source_sha256'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or shared.file_hash(path)!=checksum:raise ValueError('mechanism preregistered source differs')
    return {'schema':SCHEMA+'.protocol','preserved_A_to_D_and_E':adaptive.protocol(),
        'mechanism_plan_sha256':document['sha256'],'mechanism_plan_file_sha256':shared.file_hash(MECHANISM_PLAN),
        'additional_arm':{'label':'F','controller_api':'initialize_functions(persistent_controller=PersistentConfig or plain configuration dict)',
            'controller_config':config,'opt_in_research':True,
            'state':'direct settled learned state; exact eligible accepted public prefix cache reuse only',
            'continuation':'public receipts update predictors; recorded decisions govern remaining ranked search and abstention',
            'verification':'unchanged WITNESS and independent final contract; private labels never train',
            'ceilings':dict(adaptive.original.BOUNDS)},
        'whole_mission_cost':adaptive.whole_mission_cost_contract(),
        'prospective_memory_controls':{
            'empty':'fresh empty accepted-memory store',
            'warm':'validated current source-distinct accepted public memory',
            'expired':'same store beyond its registered admissible epoch; no expired latent state retained',
            'foreign_scope':'cross-adapter evidence must be refused, not treated as transferable history',
            'shuffled':'independently registered permutation of admissible public training observations; no relabelled private outcomes',
            'state_policies':['selectivewarm','fullwarm','cold'],
            'status':'DESIGN_ONLY; executable matched schedule and any shuffled-store transformation require independent registration'},
        'prospective_contrasts':{'primary':'F versus existing D and E, independent accepted repair rate versus whole-mission measured CPU',
            'unit':'upstream repository; repeated seeds are not independent repository observations',
            'status':'NOT_AN_EXECUTABLE_PREREGISTRATION; no estimator or efficacy threshold inferred from mechanism results'},
        'corpus':{'independent_manifest_sha256':None,'training_contract_sha256':None,'private_contract_sha256':None,
            'status':'MISSING_INDEPENDENT_CURATED_CONTRACTS','tasks_registered':0},
        'development_exclusions':sorted(adaptive.exposed_repositories()),
        'old_in_process_behavior':'AdaptiveController already retains inactive learners during ordinary switching; its snapshot/load reconstructs them.',
        'new_state_scope':'direct durable restoration; cold is an explicit discard-on-switch control, not original D',
        'coding_advantage':'NOT_ESTABLISHED','cross_repository_transfer':'NOT_ESTABLISHED',
        'evaluation_updates':False,'private_contracts_opened':False}


def code_identity():
    names=('scripts/experiment_repository_temporal_v18.py','nomad/persistent.py','nomad/platform_cli.py',
           'experiments/PLAN_TEMPORAL_V018.json')
    return {**adaptive.code_identity(),**{name:shared.file_hash(ROOT/name) for name in names}}


def freeze_design(output):
    payload={'schema':SCHEMA+'.design-only','protocol':protocol(),'source_sha256':code_identity(),
        'status':'AWAITING_NATIVE_QUALIFICATION_AND_INDEPENDENT_CORPUS','tasks_registered':0,
        'private_contracts_opened':False}
    document={'payload':payload,'sha256':shared.digest(payload)};shared.write_new(output,document);return document


def validate_design(document):
    payload=document.get('payload')
    if (type(payload) is not dict or document.get('sha256')!=shared.digest(payload)
            or payload.get('schema')!=SCHEMA+'.design-only' or payload.get('protocol')!=protocol()
            or payload.get('source_sha256')!=code_identity()):raise ValueError('persistent design/source changed')
    return payload


def refusal(document,output):
    reasons=[]
    if document is None:reasons.append('source-bound persistent repository design absent')
    else:
        try:validate_design(document)
        except (ValueError,KeyError,TypeError,OSError) as error:reasons.append(str(error))
    reasons.extend(['actual native containment and recovery qualification for the persistent mission stages is absent',
        'aggregate controller/Linux-worker CPU, hard total budgets and strict peak memory are unqualified',
        'independent curated cross-repository public/private contracts and executable matched F/memory-control schedule are absent'])
    result={'schema':SCHEMA+'.run','status':'HOLD','execution':'NOT_RUN','reasons':reasons,
        'design_sha256':document.get('sha256') if isinstance(document,dict) else None,
        'source_sha256':code_identity(),'trials':[],'private_contracts_opened':False,'repository_code_executed':False,
        'independent_corpus_sha256':None,'coding_advantage':'NOT_ESTABLISHED','cross_repository_transfer':'NOT_ESTABLISHED'}
    result['receipt_sha256']=shared.digest(result);shared.write_new(output,result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    child=sub.add_parser('protocol');child.add_argument('--output',type=Path,required=True)
    child=sub.add_parser('run');child.add_argument('--design',type=Path);child.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    result=freeze_design(args.output) if args.action=='protocol' else refusal(shared.read_json(args.design) if args.design else None,args.output)
    print(json.dumps({'status':result.get('status',result.get('payload',{}).get('status')),'execution':result.get('execution')}))
    return 3 if result.get('status')=='HOLD' else 0


if __name__=='__main__':raise SystemExit(main())
