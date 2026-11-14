"""Development-only sealing step. Never call this from acceptance verification."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.verify_package_v16 import MANIFEST,tracked_files,sha,PARENT_SHA,BGR_SHA


def main():
    path=ROOT/MANIFEST
    if path.exists():
        raise SystemExit('release manifest already sealed; refusing overwrite')
    rec={'schema':'nomad.v0.16.manifest.v1','version':'0.16.0',
         'predecessor_sha256':PARENT_SHA,'original_bgr_sha256':BGR_SHA,
         'sha256_by_path':{k:sha(v) for k,v in sorted(tracked_files())}}
    path.write_text(json.dumps(rec,indent=2)+'\n')
    print('sealed',len(rec['sha256_by_path']),'file hashes')

if __name__=='__main__':main()
