"""NOMAD intelligence feed: versioned, self-verifying packets for other agents.

Each packet publishes what NOMAD's WORLD field currently knows, but only what
WITNESS certifies *at publish time*:

* ``blocks``: library sub-programs (typed ASTs) that occur inside at least one
  program certified in this publish run. Memory alone never publishes a block.
* ``evidence``: for every certified training family, the standalone program,
  the full task rows (public / challenge / final), the WITNESS receipt, and
  the cold-control cost on the same task and budget.
* ``scores``: twin-pair summaries from the live scoreboard and the latest
  held-out probes (field vs cold control), copied as measured.

A consumer (agent-colony, locus, anyone) verifies a packet without trusting
NOMAD: recompute ``packet_sha256``; re-run each program on the shipped rows;
re-attest with WITNESS and compare ``receipt_hash`` (attestation is
deterministic); then test the blocks against *their own* control. See
docs/FEED.md. Packets are append-only and hash-chained via ``prev_sha256``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import PACKAGE_ROOT, data_root
from .world import WorldPrior, WorldTask, _freeze, certify, evaluate, render, run, subtrees, Invalid
from .world_tasks import all_training, domain_of

SCHEMA = "nomad.feed.packet.v1"
MANIFEST_SCHEMA = "nomad.feed.manifest.v1"
KEEP = 48                 # packets kept on disk (manifest keeps every hash)
PUBLISH_EVERY_MIN = 240.0  # ~45 KB per packet; bounded git growth
BUDGET = 20000


def feed_root() -> Path:
    """NOMAD_FEED, else <data>/feed when NOMAD_DATA redirects data (tests), else <repo>/feed."""
    if os.environ.get("NOMAD_FEED"):
        return Path(os.environ["NOMAD_FEED"])
    if os.environ.get("NOMAD_DATA"):
        return data_root() / "feed"
    return PACKAGE_ROOT / "feed"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def packet_hash(packet: dict) -> str:
    body = {k: v for k, v in packet.items() if k != "packet_sha256"}
    return hashlib.sha256(canonical(body)).hexdigest()


def _jsonable(v: Any) -> Any:
    if isinstance(v, tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


def task_to_json(t: WorldTask) -> dict:
    rows = lambda rs: [[_jsonable(r), _jsonable(e)] for r, e in rs]  # noqa: E731
    return {"task_id": t.task_id, "family": t.family, "opset": t.opset,
            "inputs": [list(i) for i in t.inputs], "out": t.out,
            "public": rows(t.public), "challenge": rows(t.challenge), "final": rows(t.final),
            "level": t.level}


def task_from_json(d: dict) -> WorldTask:
    rows = lambda rs: tuple(({k: _freeze(v) for k, v in r.items()}, _freeze(e)) for r, e in rs)  # noqa: E731
    return WorldTask(d["task_id"], d["family"], d["opset"], tuple(tuple(i) for i in d["inputs"]),
                     d["out"], rows(d["public"]), rows(d["challenge"]), rows(d["final"]),
                     int(d.get("level", 0)))


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _scores() -> dict:
    from .advantage import twin_summary
    rows = _read_jsonl(data_root() / "scoreboard.jsonl")
    world = [r for r in rows if r.get("kind") == "world-certified"]
    genesis = [r for r in rows if r.get("kind") != "world-certified"]

    def arm_costs(rs: list[dict]) -> dict:
        both = [r for r in rs if r.get("treatment") and r.get("control")
                and "control_evaluations" in r and "treatment_evaluations" in r]
        if not both:
            return {"pairs_with_cost": 0}
        c = sum(int(r["control_evaluations"]) for r in both)
        t = sum(int(r["treatment_evaluations"]) for r in both)
        return {"pairs_with_cost": len(both), "control_evaluations": c, "treatment_evaluations": t,
                "treatment_over_control": round(t / max(1, c), 4)}

    held = {}
    hp = data_root() / "continuous" / "world_heldout.json"
    if hp.exists():
        try:
            probes = json.loads(hp.read_text(encoding="utf-8")).get("probes", {})
        except json.JSONDecodeError:
            probes = {}
        for name, p in probes.items():
            held[name] = {"max_eval": p.get("max_eval"), "cold": p.get("cold"),
                          "field": {k: p.get("field", {}).get(k) for k in ("certified", "evaluations", "candidate")},
                          "field_beats_control": p.get("field_beats_control")}
    return {"world_twin": {**twin_summary(world), **arm_costs(world)},
            "genesis_twin": {**twin_summary(genesis), **arm_costs(genesis)},
            "heldout": held,
            "note": "Copied from the live scoreboard and the last held-out probe; descriptive, not certified."}


def _git_head() -> str | None:
    try:
        from . import hostgit
        if hostgit.available():
            return hostgit.git("rev-parse", "HEAD", check=False).stdout.strip() or None
    except Exception:
        return None
    return None


def manifest_path() -> Path:
    return feed_root() / "manifest.json"


def load_manifest() -> dict:
    p = manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"schema": MANIFEST_SCHEMA, "latest": 0, "packets": []}


def build(prior: WorldPrior | None = None) -> dict:
    """Re-certify every training family with the current field and assemble a packet."""
    from .world_loop import load_world_prior
    from .field_queue import field_version
    prior = prior if prior is not None else load_world_prior()
    library = dict(prior.library)
    evidence = []
    for t in all_training():
        cold, _ = evaluate(t, max_eval=BUDGET)
        ev, receipt = evaluate(t, prior=prior, max_eval=BUDGET)
        if not (ev.certified and receipt is not None and receipt.verify_checksum()):
            continue
        evidence.append({
            "task": task_to_json(t), "domain": domain_of(t.family),
            "program": ev.tree, "rendered": ev.candidate, "final_correct": ev.final_correct,
            "receipt": _jsonable(receipt.payload_without_hash()) | {"receipt_hash": receipt.receipt_hash},
            "control": {"certified": cold.certified, "evaluations": cold.evaluations},
            "treatment": {"certified": True, "evaluations": ev.evaluations,
                          "library_used": sorted(set(ev.library_used))},
            "budget": BUDGET,
        })
    blocks = []
    for name in sorted(library):
        tree = library[name]
        used_in = [e["task"]["task_id"] for e in evidence if tree in subtrees(e["program"])]
        if not used_in:
            continue  # not certified this run -> not published
        blocks.append({"block_id": name, "tree": tree, "rendered": render(tree),
                       "signature": prior.library_sig.get(name), "uses": round(prior.library_uses.get(name, 0.0), 4),
                       "certified_in": used_in,
                       "tree_sha256": hashlib.sha256(canonical(tree)).hexdigest()})
    man = load_manifest()
    prev = man["packets"][-1]["sha256"] if man["packets"] else None
    packet = {
        "schema": SCHEMA, "feed_version": int(man["latest"]) + 1, "published": _now(),
        "prev_sha256": prev,
        "source": {"repo": "jacksonjp0311-gif/NOMAD", "commit": _git_head(), "field_version": field_version(),
                   "world_witnessed": prior.witnessed, "host": os.environ.get("NOMAD_HOST_ID")},
        "language": {"ast": "nomad.world DSL v1: [op, *children] | ['var', name] | ['const', value]",
                     "interpreter": "nomad.world.run", "witness": "nomad-witness-world-v1"},
        "blocks": blocks, "evidence": evidence, "scores": _scores(),
        "verification": {
            "packet": "sha256 of canonical JSON (sorted keys, no spaces) of the packet without packet_sha256",
            "evidence": "re-run program on public/challenge/final rows; re-attest with WITNESS; receipt_hash must match",
            "blocks": "each block must be a subtree of a program in certified_in",
            "control": "consumers compare blocks against their own cold control on their own tasks",
            "cli": "python -m nomad.feed verify <packet.json>",
        },
        "boundaries": "Tiny typed programs (<= 7 nodes). Certified on frozen rows only; not general coding.",
    }
    packet["packet_sha256"] = packet_hash(packet)
    return packet


def verify(packet: dict) -> dict:
    """Independently verify a packet. Returns {ok, checks, failures}."""
    failures: list[str] = []
    checks = 0
    if packet.get("schema") != SCHEMA:
        failures.append("schema")
    checks += 1
    if packet_hash(packet) != packet.get("packet_sha256"):
        failures.append("packet_sha256")
    from .witness import WitnessReceipt
    progs = {}
    for e in packet.get("evidence", []):
        checks += 1
        tid = e.get("task", {}).get("task_id")
        try:
            task = task_from_json(e["task"])
            receipt, public_ok, final_ok = certify(task, e["program"])
        except (Invalid, KeyError, TypeError, ValueError) as exc:
            failures.append(f"evidence:{tid}:{type(exc).__name__}")
            continue
        if receipt is None or not receipt.supported or not public_ok or not final_ok:
            failures.append(f"evidence:{tid}:not_certified_on_rows")
            continue
        if receipt.receipt_hash != e.get("receipt", {}).get("receipt_hash"):
            failures.append(f"evidence:{tid}:receipt_hash_mismatch")
            continue
        try:
            shipped = WitnessReceipt(**e["receipt"])
            if not shipped.verify_checksum():
                failures.append(f"evidence:{tid}:receipt_checksum")
                continue
        except TypeError:
            failures.append(f"evidence:{tid}:receipt_fields")
            continue
        progs[tid] = e["program"]
    for b in packet.get("blocks", []):
        checks += 1
        if hashlib.sha256(canonical(b["tree"])).hexdigest() != b.get("tree_sha256"):
            failures.append(f"block:{b.get('block_id')}:tree_sha256")
            continue
        if not any(tid in progs and b["tree"] in subtrees(progs[tid]) for tid in b.get("certified_in", [])):
            failures.append(f"block:{b.get('block_id')}:no_certified_use")
    return {"ok": not failures, "checks": checks, "failures": failures}


def publish(prior: WorldPrior | None = None) -> dict:
    """Build, self-verify, and append a packet. Never publishes a packet that fails verify."""
    packet = build(prior)
    v = verify(packet)
    if not v["ok"]:
        return {"published": False, "reason": "self_verify_failed", "failures": v["failures"][:20]}
    root = feed_root()
    (root / "packets").mkdir(parents=True, exist_ok=True)
    name = f"{packet['feed_version']:06d}.json"
    tmp = root / "packets" / (name + ".tmp")
    tmp.write_text(json.dumps(packet, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, root / "packets" / name)
    latest = root / "latest.json"
    tmp = root / "latest.json.tmp"
    tmp.write_text(json.dumps(packet, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, latest)
    man = load_manifest()
    man["latest"] = packet["feed_version"]
    man["updated"] = packet["published"]
    man["packets"].append({"feed_version": packet["feed_version"], "file": f"packets/{name}",
                           "sha256": packet["packet_sha256"], "published": packet["published"],
                           "blocks": len(packet["blocks"]), "evidence": len(packet["evidence"])})
    for old in man["packets"][:-KEEP]:
        f = root / old["file"]
        if f.exists():
            f.unlink()
        old["file"] = None  # hash stays in the chain; file pruned
    tmp = root / "manifest.json.tmp"
    tmp.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path())
    return {"published": True, "feed_version": packet["feed_version"], "sha256": packet["packet_sha256"],
            "blocks": len(packet["blocks"]), "evidence": len(packet["evidence"]), "checks": v["checks"]}


def due(now: datetime | None = None) -> bool:
    man = load_manifest()
    if not man.get("updated"):
        return True
    now = now or datetime.now(timezone.utc)
    last = datetime.strptime(man["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (now - last).total_seconds() >= PUBLISH_EVERY_MIN * 60


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "publish"
    if cmd == "publish":
        print(json.dumps(publish()))
        return 0
    if cmd == "verify":
        path = Path(argv[1]) if len(argv) > 1 else feed_root() / "latest.json"
        rep = verify(json.loads(path.read_text(encoding="utf-8")))
        print(json.dumps(rep))
        return 0 if rep["ok"] else 1
    if cmd == "build":
        print(json.dumps(build(), indent=1, sort_keys=True))
        return 0
    print("usage: python -m nomad.feed [publish|verify [packet.json]|build]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
