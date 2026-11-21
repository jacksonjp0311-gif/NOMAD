"""NOMAD body: the long-lived, host-agnostic runtime.

    python -m nomad.body --hours 5.5 --push

runs identically on a GitHub runner, a Windows desktop, or any CPU host
with a clone of the repository. One loop, in process:

    proposer -> awake pair (control vs field) + WORLD pair -> packet queue
    -> WITNESS receipts -> sleep learner (every few cycles) -> field
    -> checkpoint: retention, organism health, lease heartbeat,
       dream journal (observational; NOMAD_DREAMLOG),
       evolve guard (git revert on live regression) and, when due, one
       test-gated genome mutation; commit data/ and push (rebase-retry).

A single-body lease (data/lease.json) keeps two hosts from writing at once;
a host takes over only from a released or stale lease. Without --push the
body runs locally and leaves commits for you to push later.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from . import hostgit, lease, retention


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _out(key: str, value: str) -> None:
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"{key}={value}\n")


def evolve_step(*, push: bool) -> dict[str, Any]:
    """Guard the last accepted genome change, then maybe evolve one gene."""
    from . import evolve
    out: dict[str, Any] = {"guard": evolve.guard()}
    decision = out["guard"].get("decision")
    if decision in ("keep", "revert") and push:
        gid = out["guard"]["id"]
        hostgit.commit(f"nomad-evolve-log: guard {decision} {gid}", ["data/evolution.jsonl"])
        if decision == "revert":
            sha = hostgit.find_commit(f"^nomad-evolve: {gid}")
            if sha:
                out["reverted"] = hostgit.revert(sha, f"nomad-revert: {gid} live twin regression (reverts {sha[:7]})")
    from . import selfedit
    if selfedit.should():
        # SELFEDIT sandbox (docs/SELFEDIT.md): one invention-gene step at this checkpoint, instead of evolve
        res = selfedit.attempt()
        out["selfedit"] = {k: res.get(k) for k in ("accepted", "reason", "gene", "id", "before", "after",
                                                   "dev_before", "dev_after", "sandbox_clean")}
        if push:
            hostgit.commit(f"nomad-evolve-log: selfedit {res.get('gene')} accepted={res.get('accepted')}"
                           f" ({res.get('reason') or 'advanced'})", ["data/evolution.jsonl"])
            if res.get("accepted"):
                g = res["gene"]
                hostgit.commit(f"nomad-evolve: {res['id']} selfedit {g} {res['before'][g]} -> {res['after'][g]}"
                               f" (dev {res['dev_before']['certified']} -> {res['dev_after']['certified']},"
                               f" keep + replay no loss, tests passed)", ["data/genome.json"])
        return out
    if evolve.should_evolve():
        res = evolve.evolve()
        out["evolve"] = {k: res.get(k) for k in ("accepted", "reason", "gene", "id", "before", "after")}
        if push:
            hostgit.commit(f"nomad-evolve-log: attempt {res.get('gene')} accepted={res.get('accepted')}",
                           ["data/evolution.jsonl"])
            if res.get("accepted"):
                hostgit.commit(f"nomad-evolve: {res['id']} {res['gene']} (benchmark better, tests passed)",
                               ["data/genome.json"])
    return out


def run(hours: float, *, push: bool = False, checkpoint_min: float = 10.0, cycle_gap_s: float = 15.0,
        sleep_every: int = 3, stale_min: float = lease.STALE_MIN, max_cycles: int | None = None,
        evolve: bool = True, feed_on: bool = True, holder_status: str | None = None) -> dict[str, Any]:
    from .continuous import pair, sleep
    from .organism import log_event, status

    me = lease.host_id()
    use_git = push and hostgit.available()
    if use_git:
        hostgit.pull()
    if lease.must_stand_by(me, stale_min, holder_status):
        held = lease.read()
        print(json.dumps({"body": "standby", "reason": "lease held", "holder": held}), flush=True)
        _out("successor", "no")
        return {"status": "standby", "holder": held}
    started = _now()
    prev = lease.read()
    if prev and not prev.get("released") and prev.get("host") != me:
        log_event("lease_takeover", previous=prev.get("host"), age_min=lease.age_min(prev),
                  holder_status=holder_status)
    lease.write(me, started=started, cycles=0)
    if use_git:
        hostgit.commit(f"nomad-body: lease acquired by {me}", ["data/"])
        hostgit.sync()
        if lease.held_by_other(me, stale_min):  # lost a race to another host
            _out("successor", "no")
            return {"status": "standby", "reason": "lost lease race"}

    t0 = time.time()
    deadline = t0 + hours * 3600.0
    cycles = sleeps = checkpoints = 0
    last_ckpt = time.time()
    stop_reason = "time"

    def checkpoint(final: bool = False) -> bool:
        nonlocal checkpoints, last_ckpt
        checkpoints += 1
        elapsed_h = max(1e-9, (time.time() - t0) / 3600.0)
        retention.trim()
        if evolve:
            try:
                ev = evolve_step(push=use_git)
            except Exception as exc:  # the body must not die on an evolve failure
                ev = {"error": repr(exc)[:300]}
        else:
            ev = None
        fd = None
        if feed_on:
            try:
                from . import feed
                if feed.due():
                    fd = feed.publish()
            except Exception as exc:  # the body must not die on a feed failure
                fd = {"error": repr(exc)[:300]}
        dl = None
        try:
            from . import dreamlog
            if dreamlog.due():
                dl = dreamlog.safe_publish(source="checkpoint")
        except Exception as exc:  # the body must not die on a journal failure
            dl = {"error": repr(exc)[:300]}
        lease.write(me, started=started, released=final, cycles=cycles,
                    cycles_per_hour=round(cycles / elapsed_h, 1), checkpoints=checkpoints)
        rep = status()
        print(json.dumps({"checkpoint": checkpoints, "cycles": cycles, "sleeps": sleeps,
                          "cycles_per_hour": round(cycles / elapsed_h, 1), "evolve": ev, "feed": fd,
                          "dreamlog": dl,
                          "world_heldout": rep["remember"]["world_heldout"],
                          "field_version": rep["remember"]["field_version"], "ts": _now()}, default=str), flush=True)
        last_ckpt = time.time()
        if use_git:
            hostgit.commit(f"nomad-body: checkpoint {checkpoints} ({cycles} cycles){' final' if final else ''}", ["data/", "feed/"])
            hostgit.sync()
            if lease.held_by_other(me, stale_min):
                return False
        return True

    while time.time() < deadline - 90:
        if max_cycles is not None and cycles >= max_cycles:
            stop_reason = "max_cycles"
            break
        try:
            pair()
            cycles += 1
            if cycles % sleep_every == 0:
                sleep(arm="treatment")
                sleeps += 1
        except Exception as exc:  # log and keep living; WITNESS gates still apply
            log_event("body_cycle_error", note=repr(exc)[:300])
        if time.time() - last_ckpt >= checkpoint_min * 60:
            if not checkpoint():
                stop_reason = "lease_lost"
                break
        if cycle_gap_s > 0:
            time.sleep(cycle_gap_s)
    if stop_reason != "lease_lost":
        try:
            sleep(arm="treatment")
            sleeps += 1
        except Exception as exc:
            log_event("body_cycle_error", note=repr(exc)[:300])
        checkpoint(final=True)
    elapsed_h = (time.time() - t0) / 3600.0
    summary = {"status": "done", "stop": stop_reason, "host": me, "cycles": cycles, "sleeps": sleeps,
               "checkpoints": checkpoints, "hours": round(elapsed_h, 3),
               "cycles_per_hour": round(cycles / max(1e-9, elapsed_h), 1)}
    _out("successor", "yes" if stop_reason == "time" else "no")
    print(json.dumps(summary), flush=True)
    return summary


def gate(stale_min: float = lease.STALE_MIN, holder_status: str | None = None) -> dict[str, Any]:
    """Decide before the run whether this host will stand by.

    The workflow queues its successor only when ``standby`` is false, so a
    standby run never chains another run (Nov 21 2026 restart storm). Same
    rule as ``run``: a released, stale or orphaned lease is taken over.
    """
    me = lease.host_id()
    standby = lease.must_stand_by(me, stale_min, holder_status)
    cur = lease.read()
    _out("standby", "yes" if standby else "no")
    return {"standby": standby, "me": me, "holder_status": holder_status,
            "age_min": lease.age_min(cur), "lease": cur}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="NOMAD long-lived body (runs on any CPU host)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="run the body loop (default)")
    for p in (ap, r):
        p.add_argument("--hours", type=float, default=1.0)
        p.add_argument("--push", action="store_true", help="pull/commit/push data via git")
        p.add_argument("--checkpoint-min", type=float, default=10.0)
        p.add_argument("--cycle-gap-s", type=float, default=15.0)
        p.add_argument("--sleep-every", type=int, default=3)
        p.add_argument("--stale-min", type=float, default=lease.STALE_MIN)
        p.add_argument("--max-cycles", type=int, default=None)
        p.add_argument("--no-evolve", action="store_true")
        p.add_argument("--holder-status", default=None,
                       help="GitHub run status of the lease holder (completed => take over)")
    l = sub.add_parser("lease", help="print lease status; exit 0 either way")
    l.add_argument("--stale-min", type=float, default=lease.STALE_MIN)
    g = sub.add_parser("gate", help="will this host stand by? sets GITHUB_OUTPUT standby=yes|no")
    g.add_argument("--stale-min", type=float, default=lease.STALE_MIN)
    g.add_argument("--holder-status", default=None)
    e = sub.add_parser("evolve-step", help="guard + maybe evolve, for fallback sleep runs")
    e.add_argument("--push", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "lease":
        cur = lease.read()
        alive = lease.alive(cur, a.stale_min)
        print(json.dumps({"alive": alive, "age_min": lease.age_min(cur), "lease": cur}))
        _out("alive", "true" if alive else "false")
        return 0
    if a.cmd == "gate":
        print(json.dumps(gate(a.stale_min, a.holder_status or None)))
        return 0
    if a.cmd == "evolve-step":
        print(json.dumps(evolve_step(push=a.push), default=str))
        if a.push:
            hostgit.sync()
        return 0
    res = run(a.hours, push=a.push, checkpoint_min=a.checkpoint_min, cycle_gap_s=a.cycle_gap_s,
              sleep_every=a.sleep_every, stale_min=a.stale_min, max_cycles=a.max_cycles,
              evolve=not a.no_evolve, holder_status=a.holder_status or None)
    return 0 if res.get("status") in ("done", "standby") else 1


if __name__ == "__main__":
    raise SystemExit(main())
