"""Explicit first-time sealing; acceptance MUST run verify_package_v17.py instead."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.verify_package_v17 import MANIFEST,FREEZE,PARENT_SHA,BGR_SHA,tracked_files,sha
SOURCE=(
 'nomad/supervised.py','nomad/isolation.py','nomad/archive_guard.py',
 'nomad/effects.py','nomad/protect_cli.py','nomad/mission_runtime.py',
 'tests/test_security_v17.py',
)

def main():
    if (ROOT/MANIFEST).exists() or (ROOT/FREEZE).exists():
        raise SystemExit('frozen source or manifest exists; refusing overwrite')
    freeze={'schema':'nomad.v0.17.source-freeze.v1',
            'note':'post-development engineering integrity freeze, NOT a preregistered blind evaluation',
            'sha256_by_path':{rel:sha(ROOT/rel) for rel in SOURCE}}
    (ROOT/FREEZE).write_text(json.dumps(freeze,indent=2)+'\n')
    rec={'schema':'nomad.v0.17.manifest.v1','version':'0.17.0',
         'predecessor_sha256':PARENT_SHA,'original_bgr_sha256':BGR_SHA,
         'sha256_by_path':{rel:sha(path) for rel,path in sorted(tracked_files())}}
    (ROOT/MANIFEST).write_text(json.dumps(rec,indent=2)+'\n')
    print('sealed',len(rec['sha256_by_path']),'file hashes and',len(SOURCE),'source hashes')

if __name__=='__main__':main()
