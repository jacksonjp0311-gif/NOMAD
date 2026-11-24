"""SELFEDIT: the self-edit sandbox (docs/SELFEDIT.md). Switch ``NOMAD_SELFEDIT``.

Same-gene refuse: after two consecutive test failures on the same gene from
the same genome, that gene is tabu until a different gene is accepted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any

from . import evolve, genome
from .paths import PACKAGE_ROOT, data_root

DEV_SEED = 7
BUDGET = 10000
MAX_SIZE = 7
WINDOW_MAX = 24
SELFEDIT_EVERY_MIN = 60
SAME_GENE_REFUSE = 2

STEPS = {"inv_max_constants": (-2, -1, 1, 2, 4), "inv_const_depth": (-1, 1),
         "inv_rounds": (-1, 1), "inv_floor_fit": (-1, 1)}


def enabled() -> bool:
    v = os.environ.get("NOMAD_SELFEDIT", "on").strip().lower()
    return v not in ("0", "off", "false", "no")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _on:
    def __init__(self, genes: dict[str, Any]):
        self.genes = genes

    def __enter__(self):
        self.old = os.environ.get("NOMAD_SELFEDIT")
        os.environ["NOMAD_SELFEDIT"] = "on"
        self.ov = genome.override(self.genes)
        self.ov.__enter__()
        return self

    def __exit__(self, *exc):
        self.ov.__exit__(*exc)
        if self.old is None:
            os.environ.pop("NOMAD_SELFEDIT", None)
        else:
            os.environ["NOMAD_SELFEDIT"] = self.old
        return False


def _key(genes: dict[str, Any]) -> str:
    return json.dumps({k: genes[k] for k in genome.INVENT_GENES}, sort_keys=True)


def propose(genes: dict[str, Any], seed: int, tabu: set | None = None,
            gene_tabu: set | None = None) -> tuple[dict[str, Any], str]:
    rng = random.Random(f"selfedit:{seed}")
    tabu = tabu or set()
    gene_tabu = gene_tabu or set()
    for _ in range(64):
        gene = rng.choice(genome.INVENT_GENES)
        if gene in gene_tabu:
            continue
        cand = dict(genes)
        cand[gene] = genome.clamp(gene, genes[gene] + rng.choice(STEPS[gene]))
        if cand[gene] != genes[gene] and _key(cand) not in tabu:
            return cand, gene
    return dict(genes), "none"


def tabu_from_log(current: dict[str, Any], hist: list[dict] | None = None) -> set:
    """Candidates the sandbox already rejected from ``current``."""
    hist = evolve.history() if hist is None else hist
    cur = _key(current)
    return {_key(r["after"]) for r in hist
            if r.get("organ") == "selfedit" and not r.get("accepted") and r.get("before") and r.get("after")
            and _key(r["before"]) == cur and r.get("reason") not in ("tests_failed", "sandbox_wrote_live_data")}


def gene_tabu_from_log(current: dict[str, Any], hist: list[dict] | None = None) -> set:
    """Genes with two consecutive test failures from this genome."""
    hist = evolve.history() if hist is None else hist
    cur = _key(current)
    gene_fails: dict[str, int] = {}
    for r in reversed(hist):
        if r.get("organ") != "selfedit" or not r.get("before") or _key(r["before"]) != cur:
            continue
        if r.get("accepted"):
            break
        if r.get("reason") == "tests_failed" and r.get("gene"):
            gene_fails[r["gene"]] = gene_fails.get(r["gene"], 0) + 1
    return {g for g, n in gene_fails.items() if n >= SAME_GENE_REFUSE}


_FIELD: dict[str, Any] = {}


def reference_field():
    if "f" not in _FIELD:
        sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
        import bridge_suite as BS
        _FIELD["f"] = BS.fields()["trained"]
    return _FIELD["f"]


def dev_tasks(seed: int = DEV_SEED) -> list:
    from .selfedit_tasks import DEV_CATALOGUE, draw_rows, to_task
    out = []
    for i, f in enumerate(DEV_CATALOGUE):
        rows = draw_rows(f, random.Random(f"{seed}:{f.family}"))
        out.append(to_task({"task_id": f"sd-{i:02d}", "family": f.family, "inputs": list(f.inputs),
                            "rows": [[r, a] for r, a in rows]}))
    return out


def keep_tasks(seed: int = DEV_SEED) -> list:
    from . import bridge as XB
    from . import text as XT
    from . import transfer4 as T4
    out = []
    for i, f in enumerate(T4.CATALOGUE):
        rows = T4.draw_rows(f, random.Random(f"{seed}:{f.family}"))
        out.append(T4.to_task({"task_id": f"sk-{i:02d}", "family": f.family, "inputs": list(f.inputs),
                               "rows": [[r, a] for r, a in rows]}))
    for i, f in enumerate(XT.CATALOGUE):
        rows = XT.draw_rows(f, random.Random(f"{seed}:{f.family}"))
        out.append(XT.to_task({"task_id": f"st-{i:02d}", "family": f.family, "inputs": list(f.inputs),
                               "out": f.out, "rows": [[r, a] for r, a in rows]}))
    for i, f in enumerate(XB.DEV_CATALOGUE):
        rows = XB.draw_rows(f, random.Random(f"{seed}:{f.family}"))
        out.append(XB.to_task({"task_id": f"sb-{i:02d}", "family": f.family, "inputs": list(f.inputs),
                               "out": f.out, "rows": [[r, a] for r, a in rows]}))
    return out


def run_tasks(tasks: list, genes: dict[str, Any], prior, variation=None) -> dict[str, list]:
    p = copy.deepcopy(prior)
    vs = copy.deepcopy(variation)
    out = {}
    old_b = os.environ.get("NOMAD_BRIDGE")
    os.environ.setdefault("NOMAD_BRIDGE", "on")
    try:
        out = _run(tasks, genes, p, vs)
    finally:
        if old_b is None:
            os.environ.pop("NOMAD_BRIDGE", None)
    return out


def _run(tasks, genes, p, vs) -> dict[str, list]:
    from .world import evaluate
    out = {}
    with _on(genes):
        for t in tasks:
            ev = evaluate(t, prior=p, variation=vs, max_eval=BUDGET, max_size=MAX_SIZE, casesplit=True)[0]
            out[t.family] = [bool(ev.certified), int(ev.evaluations)]
    return out


def summary(per: dict[str, list]) -> dict[str, int]:
    return {"certified": sum(v[0] for v in per.values()), "evaluations": sum(v[1] for v in per.values()),
            "tasks": len(per)}


def better(a: dict, b: dict) -> bool:
    if a["certified"] != b["certified"]:
        return a["certified"] > b["certified"]
    return a["evaluations"] < b["evaluations"]


def losses(base: dict[str, list], cand: dict[str, list]) -> list[str]:
    out = []
    for k, (c, e) in base.items():
        c2, e2 = cand.get(k, [False, 10 ** 9])
        if (c and not c2) or (c and c2 and e2 > e):
            out.append(k)
    return out


def window(since: str | None, rows: list[dict] | None = None) -> dict[str, Any]:
    from .scoreboard import recent
    from .world_tasks import by_family
    rows = recent(512) if rows is None else rows
    rows = [r for r in rows if str(r.get("task", "")).startswith("world:") and (since is None or r.get("ts", "") > since)]
    fams, recorded = [], {}
    for r in rows:
        fam = r["task"].split(":", 1)[1]
        recorded[fam] = [bool(r.get("treatment")), int(r.get("treatment_evaluations") or 0)]
        if fam not in fams:
            fams.append(fam)
    fams = fams[-WINDOW_MAX:]
    tasks = [t for t in (by_family(f) for f in fams) if t is not None]
    return {"pairs": len(rows), "families": [t.family for t in tasks], "tasks": tasks,
            "recorded": {t.family: recorded[t.family] for t in tasks}}


def _data_fingerprint() -> str:
    h = hashlib.sha256()
    cont = data_root() / "continuous"
    for name in ("world_prior.json", "prior.json", "variation.json"):
        p = cont / name
        h.update(name.encode())
        h.update(p.read_bytes() if p.exists() else b"-")
    g = genome.path()
    h.update(g.read_bytes() if g.exists() else b"-")
    return h.hexdigest()


def last_attempt_ts() -> str | None:
    rows = [r for r in evolve.history() if r.get("organ") == "selfedit" and "gene" in r]
    return rows[-1]["ts"] if rows else None


def should() -> bool:
    if not enabled():
        return False
    hist = evolve.history()
    resolved = {r.get("resolves") for r in hist if r.get("resolves")}
    if any(r.get("accepted") and r.get("status") == "pending_verification" and r.get("id") not in resolved
           for r in hist):
        return False
    ts = last_attempt_ts()
    if ts is None:
        return True
    last = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() >= SELFEDIT_EVERY_MIN * 60


def step(current: dict[str, Any], seed: int, *, live_prior=None, win: dict | None = None,
         dev_field=None, tests: bool = True, dev=None, keep=None, tabu: set | None = None,
         gene_tabu: set | None = None) -> dict[str, Any]:
    cand, gene = propose(current, seed, tabu, gene_tabu)
    row: dict[str, Any] = {"organ": "selfedit", "seed": seed, "gene": gene, "before": current, "after": cand}
    if gene == "none":
        row.update(accepted=False, reason="no_change")
        return row
    p, vs = dev_field if dev_field is not None else reference_field()
    dev = dev_tasks() if dev is None else dev
    d0, d1 = run_tasks(dev, current, p, vs), run_tasks(dev, cand, p, vs)
    row.update(dev_before=summary(d0), dev_after=summary(d1), dev_losses=losses(d0, d1))
    if not better(row["dev_after"], row["dev_before"]):
        row.update(accepted=False, reason="dev_not_better")
        return row
    lost = [k for k in row["dev_losses"] if d0[k][0] and not d1[k][0]]
    if lost:
        row.update(accepted=False, reason="dev_loss", dev_lost=lost)
        return row
    keep = keep_tasks() if keep is None else keep
    k0, k1 = run_tasks(keep, current, p, vs), run_tasks(keep, cand, p, vs)
    row.update(keep_before=summary(k0), keep_after=summary(k1), keep_losses=losses(k0, k1))
    if row["keep_losses"]:
        row.update(accepted=False, reason="keep_loss")
        return row
    if win is not None and live_prior is not None and win["tasks"]:
        r0, r1 = run_tasks(win["tasks"], current, live_prior), run_tasks(win["tasks"], cand, live_prior)
        rec = win["recorded"]
        row.update(window_families=win["families"], window_pairs=win["pairs"],
                   recorded=summary(rec), replay_before=summary(r0), replay_after=summary(r1),
                   replay_losses=losses(r0, r1),
                   replay_vs_recorded={"certified_recorded": sum(v[0] for v in rec.values()),
                                       "certified_replay_after": sum(v[0] for v in r1.values())})
    else:
        row.update(window_families=[], replay_losses=[])
    if row["replay_losses"]:
        row.update(accepted=False, reason="replay_loss")
        return row
    if tests:
        ok = _tests_with(cand)
        if not ok:
            row.update(accepted=False, reason="tests_failed")
            return row
    row.update(accepted=True)
    return row


def _tests_with(cand: dict[str, Any]) -> bool:
    p = genome.path()
    old = p.read_bytes() if p.exists() else None
    try:
        genome.save(cand, note="selfedit trial")
        return evolve.run_tests()
    finally:
        if old is None:
            p.unlink(missing_ok=True)
        else:
            p.write_bytes(old)
        genome._CACHE.clear()


def attempt(*, seed: int | None = None, tests: bool = True) -> dict[str, Any]:
    from .scoreboard import recent
    from .world_loop import load_world_prior
    current = genome.load()
    if seed is None:
        seed = int(hashlib.sha256(_now().encode()).hexdigest()[:8], 16)
    fp0 = _data_fingerprint()
    win = window(last_attempt_ts())
    live = load_world_prior()
    row = step(current, seed, live_prior=live, win=win, tests=tests,
               tabu=tabu_from_log(current), gene_tabu=gene_tabu_from_log(current))
    fp1 = _data_fingerprint()
    row["ts"] = _now()
    row["sandbox_clean"] = fp0 == fp1
    if not row["sandbox_clean"]:
        row.update(accepted=False, reason="sandbox_wrote_live_data")
    if row.get("accepted"):
        genome.save(row["after"], note=f"selfedit {row['gene']} {current[row['gene']]} -> {row['after'][row['gene']]}")
        row.update(status="pending_verification", live_ratio_before=evolve.live_cost_ratio(recent(64)))
        row["id"] = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()[:10]
    evolve._log(row)
    return row


def run_offline(n: int, base_seed: int, *, dev_field=None, live_prior=None, win: dict | None = None,
                start: dict[str, Any] | None = None, tests: bool = False) -> dict[str, Any]:
    cur = dict(genome.DEFAULTS if start is None else start)
    log, tabu, gene_tabu = [], set(), set()
    for i in range(n):
        seed = int(hashlib.sha256(f"{base_seed}:{i}".encode()).hexdigest()[:8], 16)
        row = step(cur, seed, live_prior=live_prior, win=win, dev_field=dev_field, tests=tests,
                   tabu=tabu, gene_tabu=gene_tabu)
        log.append({k: row.get(k) for k in ("seed", "gene", "before", "after", "accepted", "reason",
                                            "dev_before", "dev_after", "replay_before", "replay_after",
                                            "replay_losses", "dev_losses", "keep_before", "keep_after",
                                            "keep_losses")})
        if row.get("accepted"):
            cur = dict(row["after"])
            tabu = set()
            gene_tabu = set()
        elif row.get("gene") != "none":
            tabu.add(_key(row["after"]))
            if row.get("reason") == "tests_failed":
                fails = sum(1 for r in log if r.get("gene") == row["gene"] and r.get("reason") == "tests_failed")
                if fails >= SAME_GENE_REFUSE:
                    gene_tabu.add(row["gene"])
    return {"final": cur, "steps": log, "accepted": sum(1 for r in log if r["accepted"])}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NOMAD self-edit sandbox")
    ap.add_argument("cmd", choices=("attempt", "should", "window", "offline"))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "attempt":
        out = attempt(seed=a.seed, tests=not a.no_tests)
    elif a.cmd == "should":
        out = {"should": should()}
    elif a.cmd == "window":
        w = window(last_attempt_ts())
        out = {k: v for k, v in w.items() if k != "tasks"}
    else:
        out = run_offline(a.n, a.seed or 0)
    print(json.dumps(out, indent=2, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
