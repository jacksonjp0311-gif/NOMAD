#!/usr/bin/env python3
"""Dry-run drill of NOMAD's self-revert path, end to end, without touching live main.

Clones this repo (including the current live data/) into a temp dir whose
`origin` is a throwaway bare repo, then in that clone:

1. writes an "accepted" genome change exactly as the body does
   (evolution log row + `nomad-evolve: <id>` commit of data/genome.json),
2. appends world twin rows after it (regressed, or healthy for the control
   scenario),
3. runs the real `python -m nomad.body evolve-step --push` in the clone,
4. checks: guard decision, `nomad-revert:` commit present, genome restored,
   evolution log resolved, and the revert pushed to the throwaway origin.

Usage: python3 scripts/revert_drill.py [--keep-dir]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def sh(*args: str, cwd: Path, check: bool = True, env: dict | None = None) -> str:
    p = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, env=env, timeout=600)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {p.stderr.strip()[:400]}")
    return p.stdout.strip()


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def scenario(root: Path, regress: bool) -> dict:
    bare = root / "origin.git"
    clone = root / "clone"
    sh("git", "clone", "-q", "--bare", "--no-local", str(REPO), str(bare), cwd=root)
    sh("git", "clone", "-q", str(bare), str(clone), cwd=root)
    # carry the live working-tree data (may be newer than HEAD) into the clone
    shutil.rmtree(clone / "data")
    shutil.copytree(REPO / "data", clone / "data")
    for k, v in (("user.name", "NOMAD drill"), ("user.email", "drill@localhost")):
        sh("git", "config", k, v, cwd=clone)
    sh("git", "add", "-A", "data", cwd=clone)
    sh("git", "commit", "-q", "--allow-empty", "-m", "drill: live data snapshot", cwd=clone)
    sh("git", "push", "-q", "origin", "HEAD", cwd=clone)

    env = {k: v for k, v in os.environ.items() if k not in ("NOMAD_DATA", "NOMAD_FEED", "GITHUB_TOKEN", "GH_TOKEN")}
    env["PYTHONPATH"] = str(clone)
    py = [sys.executable, "-B"]
    genome_before = (clone / "data" / "genome.json").read_text() if (clone / "data" / "genome.json").exists() else None

    # 1. accepted change, written like nomad.evolve.evolve + body.evolve_step
    t0 = datetime.now(timezone.utc) + timedelta(seconds=5)  # after every live row
    gid = f"drill{os.getpid()}{'r' if regress else 'k'}"
    probe = ("from nomad.evolve import live_cost_ratio; from nomad.scoreboard import recent;"
             "print(live_cost_ratio(recent(64)))")
    before = float(sh(*py, "-c", probe, cwd=clone, env=env) or "nan")
    genes = {"decay": 0.97, "library_k": 3, "patience": 4, "max_lag": 2}
    (clone / "data" / "genome.json").write_text(json.dumps({"genes": genes, "note": "drill"}, indent=1) + "\n")
    with open(clone / "data" / "evolution.jsonl", "a") as f:
        f.write(json.dumps({"ts": ts(t0), "seed": 0, "gene": "library_k", "id": gid, "accepted": True,
                            "status": "pending_verification", "live_ratio_before": before}) + "\n")
    sh("git", "add", "data/evolution.jsonl", cwd=clone)
    sh("git", "commit", "-q", "-m", f"nomad-evolve-log: attempt library_k accepted=True", cwd=clone)
    sh("git", "add", "data/genome.json", cwd=clone)
    sh("git", "commit", "-q", "-m", f"nomad-evolve: {gid} library_k (drill)", cwd=clone)
    evolve_sha = sh("git", "rev-parse", "HEAD", cwd=clone)

    # 2. world twin rows after the change
    with open(clone / "data" / "scoreboard.jsonl", "a") as f:
        for i in range(8):
            c = 200
            t = int(c * before * (3.0 if regress else 1.0)) or 1
            f.write(json.dumps({"ts": ts(t0 + timedelta(minutes=1 + i)), "task": f"world:drill{i}",
                                "treatment": True, "control": True, "delta": 0, "kind": "world-certified",
                                "pair_id": f"drill{i}", "treatment_evaluations": t, "control_evaluations": c,
                                "evaluations_saved": c - t, "field_version": 0}) + "\n")
    sh("git", "add", "data/scoreboard.jsonl", cwd=clone)
    sh("git", "commit", "-q", "-m", "drill: twin rows after change", cwd=clone)

    # 3. the real organ entry point the body and sleep runs use
    out = sh(*py, "-m", "nomad.body", "evolve-step", "--push", cwd=clone, env=env)
    step = json.loads(out.splitlines()[-1])

    # 4. checks
    log = sh("git", "log", "--format=%s", "-8", cwd=clone).splitlines()
    br = sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=clone)
    remote_log = sh("git", "log", "--format=%s", "-8", br, cwd=bare).splitlines()
    genome_now = (clone / "data" / "genome.json").read_text() if (clone / "data" / "genome.json").exists() else None
    hist = [json.loads(l) for l in (clone / "data" / "evolution.jsonl").read_text().splitlines() if l.strip()]
    resolved = [h for h in hist if h.get("resolves") == gid]
    want = "revert" if regress else "keep"
    checks = {
        "guard_decision": step["guard"].get("decision") == want,
        "evolution_log_resolved": len(resolved) == 1 and resolved[0]["decision"] == want,
        "revert_commit": any(s.startswith(f"nomad-revert: {gid}") for s in log) == regress,
        "genome_restored": (genome_now == genome_before) if regress else (genome_now is not None),
        "pushed_to_origin": any(s.startswith(f"nomad-evolve-log: guard {want} {gid}") for s in remote_log)
                            and (any(s.startswith(f"nomad-revert: {gid}") for s in remote_log) == regress),
        "evolve_commit_kept_in_history": evolve_sha in sh("git", "rev-list", "HEAD", cwd=clone),
    }
    return {"scenario": "regressed" if regress else "healthy", "id": gid,
            "live_ratio_before": round(before, 4), "guard": step["guard"], "reverted": step.get("reverted"),
            "evolve_attempted": "evolve" in step, "head_commits": log[:4], "checks": checks,
            "ok": all(checks.values())}


def main() -> int:
    keep = "--keep-dir" in sys.argv
    results = []
    for regress in (True, False):
        root = Path(tempfile.mkdtemp(prefix="nomad-revert-drill-"))
        try:
            results.append(scenario(root, regress))
        finally:
            if keep:
                print(f"kept {root}", file=sys.stderr)
            else:
                shutil.rmtree(root, ignore_errors=True)
    print(json.dumps(results, indent=1, default=str))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
