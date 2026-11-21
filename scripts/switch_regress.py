"""Measurement only: no per-task loss on the existing sealed suites with a switch on vs off (SELFEDIT / INVENT_TEXT criteria).

    SWITCH=NOMAD_SELFEDIT python3 scripts/switch_regress.py run OUTDIR [NAME ...]
    python3 scripts/switch_regress.py compare OUTDIR

Generalises scripts/bridge_regress.py (unchanged): the switch name comes from $SWITCH, and the BRIDGE
sealed judge is one more suite. Original notes follow.

    python3 scripts/bridge_regress.py run  OUTDIR [NAME ...]   # each judge twice (NOMAD_BRIDGE=off, on), in parallel
    python3 scripts/bridge_regress.py compare OUTDIR           # per-task and LOFO comparison, JSON to stdout

Judges: learning (deep + science hard + LOFO, no practice), transfer1, transfer2, transfer3, transfer4
(`invent2_judge --secondary` also re-runs deep / science / transfer1-3 with the INVENT arms), text.
Compare: for every per-task record of every arm, a loss = certified with the switch off but not on, or more
evaluations on; a gain = the reverse. Writes nothing into results/ (OUTDIR is the caller's choice; new files only).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGES = {
    "learning": ["scripts/learning_judge.py", "--no-practice"],
    "transfer1": ["scripts/transfer_judge.py"],
    "transfer2": ["scripts/grow_judge.py"],
    "transfer3": ["scripts/invent_judge.py"],
    "transfer4": ["scripts/invent2_judge.py"],
    "secondary4": ["scripts/invent2_judge.py", "--secondary"],
    "text": ["scripts/text_judge.py"],
    "bridge": ["scripts/bridge_judge.py"],
    "text_invent": ["scripts/text_invent_judge.py"],   # INVENT_TEXT sealed suite (SELFEDIT round 2)
    "route5": ["scripts/route_judge.py"],              # TRANSFER-5 sealed suite (SELFEDIT round 2)
    "transfer6": ["scripts/graph_judge.py"],           # TRANSFER-6 sealed suite (TEXT_CHAIN)
    "selfedit2": ["scripts/selfedit_judge.py", "--round", "2"],   # SELFEDIT round-2 sealed suite (TEXT_CHAIN)
    "text_chain": ["scripts/text_chain_judge.py"],     # TEXT_CHAIN sealed suite (ROUTE_CUT)
    "meaning": ["scripts/meaning_judge.py"],           # MEANING sealed suite (ROUTE_CUT addendum)
    "inflect": ["scripts/inflect_judge.py"],           # INFLECT sealed suite (this step)
}


def run(outdir: Path, names: list[str]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = [(n, f) for n in (names or list(JUDGES)) for f in ("off", "on")]

    def one(job):
        n, f = job
        dest = outdir / f"{n}_{f}.json"
        if dest.exists():
            return job, 0
        env = dict(os.environ, **{os.environ["SWITCH"]: f})
        with open(dest.with_suffix(".tmp"), "w") as fh:
            rc = subprocess.run([sys.executable] + JUDGES[n], cwd=ROOT, env=env, stdout=fh).returncode
        if rc == 0:
            dest.with_suffix(".tmp").rename(dest)
        return job, rc

    with ThreadPoolExecutor(max_workers=int(os.environ.get("BRIDGE_JOBS", "8"))) as ex:
        for job, rc in ex.map(one, jobs):
            print(job, "rc", rc, file=sys.stderr)


def _records(o, path=""):
    """Yield (path, {arm: [certified, evals, ...]}) for every per-task block."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("per_task") and isinstance(v, dict):
                for fam, arms in v.items():
                    yield f"{path}/{fam}", arms
            else:
                yield from _records(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _records(v, f"{path}[{i}]")


def _lofo(o, path=""):
    if isinstance(o, dict):
        if "totals" in o and "worst_ratio" in o and "lofo" in path:
            yield path, o
        for k, v in o.items():
            yield from _lofo(v, f"{path}/{k}")


def compare(outdir: Path) -> dict:
    out = {}
    for off in sorted(outdir.glob("*_off.json")):
        n = off.name[:-9]
        on = outdir / f"{n}_on.json"
        if not on.exists():
            continue
        a, b = json.loads(off.read_text()), json.loads(on.read_text())
        ra, rb = dict(_records(a)), dict(_records(b))
        loss, gain, same, total_off, total_on = [], [], 0, 0, 0
        for k, arms in ra.items():
            for arm, rec in arms.items():
                other = rb.get(k, {}).get(arm)
                if other is None:
                    loss.append([k, arm, "missing"])
                    continue
                total_off += bool(rec[0])
                total_on += bool(other[0])
                if rec[0] and not other[0]:
                    loss.append([k, arm, "certified off, not on"])
                elif rec[0] and other[0] and other[1] > rec[1]:
                    loss.append([k, arm, f"evals {rec[1]} -> {other[1]}"])
                elif other[0] and not rec[0]:
                    gain.append([k, arm, "certified on, not off"])
                elif (rec[0] and other[0] and other[1] < rec[1]):
                    gain.append([k, arm, f"evals {rec[1]} -> {other[1]}"])
                else:
                    same += 1
        lof = {p: [r["totals"], r["worst_ratio"]] for p, r in _lofo(b)}
        lof_off = {p: [r["totals"], r["worst_ratio"]] for p, r in _lofo(a)}
        out[n] = {"records": len(ra), "unchanged": same, "losses": loss, "gains": gain,
                  "certified_total_off_on": [total_off, total_on],
                  "lofo_off": lof_off, "lofo_on": lof}
    return out


if __name__ == "__main__":
    cmd, outdir = sys.argv[1], Path(sys.argv[2])
    if cmd == "run":
        run(outdir, sys.argv[3:])
    else:
        print(json.dumps(compare(outdir), indent=1))
