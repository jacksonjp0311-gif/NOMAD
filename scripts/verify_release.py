"""Current NOMAD version verification wrapper (read-only)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.verify_package_v11 import main
if __name__=='__main__':raise SystemExit(main())
