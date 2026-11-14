"""Run source-language training ONLY; no target-language holdout generation."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from nomad.simulation_v13 import TRAIN_SEEDS,train_language


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error('refusing to overwrite a nonempty evidence directory')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for language,seeds in TRAIN_SEEDS.items():
        memory,report=train_language(language,seeds)
        memory.save(args.output_dir/f'{language}-memory.json')
        (args.output_dir/f'{language}-training.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        print(language,'witnessed',len(memory.events),'of',report['attempted'],'training cases')
    return 0
if __name__=='__main__':raise SystemExit(main())
