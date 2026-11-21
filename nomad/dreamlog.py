"""NOMAD dream journal: a message board written in sleep from certified evidence.

Entries are composed by a deterministic generative grammar seeded by a hash
of the entry's evidence. They are reflection, not certified claims, and they
are not written by a language model. The organ is observational: it reads
existing logs and writes only ``data/dreams/journal.jsonl`` and
``feed/DREAMS.md``. It never touches search, the field prior, or learning.
Switch: ``NOMAD_DREAMLOG`` (default on). See docs/DREAMLOG.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import PACKAGE_ROOT, data_root

SCHEMA = "nomad.dream.v1"
MIN_INTERVAL_SEC = 30 * 60
JOURNAL_MAX_BYTES = 1_500_000
JOURNAL_MAX_ENTRIES = 1500
BOARD_KEEP = 100
BOARD_NAME = "DREAMS.md"

INV_GENES = {"inv_max_constants", "inv_const_depth", "inv_rounds", "inv_floor_fit"}

BOARD_HEADER = """# NOMAD dream journal

These entries are composed by NOMAD's own deterministic generative grammar from its evidence logs. They are not written by a language model. They are reflection, not certified claims. WITNESS and the twin scoreboard remain the only sources of certified fact. The switch `NOMAD_DREAMLOG` (default on) only writes this board; it does not affect search or learning.

Newest first. The last %d entries are shown. The append-only log lives at `data/dreams/journal.jsonl`.

---
""" % BOARD_KEEP


def enabled() -> bool:
    """NOMAD_DREAMLOG: write the dream journal. Default on; observational only."""
    v = os.environ.get("NOMAD_DREAMLOG", "on").strip().lower()
    return v not in ("off", "0", "false", "no")


def journal_path() -> Path:
    return data_root() / "dreams" / "journal.jsonl"


def _feed_root() -> Path:
    """Same rule as nomad.feed.feed_root, inlined so this organ does not import world."""
    if os.environ.get("NOMAD_FEED"):
        return Path(os.environ["NOMAD_FEED"])
    if os.environ.get("NOMAD_DATA"):
        return data_root() / "feed"
    return PACKAGE_ROOT / "feed"


def board_path() -> Path:
    return _feed_root() / BOARD_NAME


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(ts, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short(ts: str) -> str:
    d = _parse_ts(ts)
    if d is None:
        return ts
    return f"{d.day} {d.strftime('%B %Y at %H:%M UTC')}"


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode("utf-8")


def content_hash(evidence: dict) -> str:
    return hashlib.sha256(canonical(evidence)).hexdigest()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def load_entries() -> list[dict]:
    return _read_jsonl(journal_path())


# --- pretty-print of certified primitives (metaphors, not new claims) -----

_INFIX = {"add": ("+", 1, 1, 2), "sub": ("-", 1, 1, 2),
          "mul": ("·", 2, 2, 2), "div": ("//", 2, 2, 3),
          "mod": ("%", 2, 2, 3), "concat": ("∥", 1, 1, 1)}


def pretty_tree(tree: Any) -> str:
    """Algebraic rendering: ``add(mul(x,x), y)`` -> ``x·x + y``."""
    if isinstance(tree, str):
        parsed = _parse_render(tree)
        return pretty_tree(parsed) if parsed is not None else tree
    if not isinstance(tree, (list, tuple)) or not tree:
        return repr(tree)
    tag = tree[0]
    if tag == "var":
        return str(tree[1])
    if tag == "const":
        return str(tree[1])
    if tag == "lib":
        return f"@{tree[1]}"
    if tag in _INFIX and len(tree) == 3:
        op, prec, lbp, rbp = _INFIX[tag]
        gap = " " if tag in ("add", "sub") else ""
        return _wrap(tree[1], lbp) + f"{gap}{op}{gap}" + _wrap(tree[2], rbp)
    return f"{tag}(" + ", ".join(pretty_tree(c) for c in tree[1:]) + ")"


def _wrap(child: Any, need: int) -> str:
    s = pretty_tree(child)
    if isinstance(child, (list, tuple)) and child and child[0] in _INFIX:
        child_prec = _INFIX[child[0]][1]
        if child_prec < need:
            return f"({s})"
    return s


def _parse_render(s: str) -> list | None:
    """Parse ``world.render`` strings (``add(mul(x, x), y)``) back to trees."""
    s = s.strip()
    try:
        tree, i = _parse_atom(s, 0)
        if i == len(s) and tree is not None:
            return tree
    except (ValueError, IndexError):
        return None
    return None


def _parse_atom(s: str, i: int) -> tuple[Any, int]:
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        raise ValueError("eof")
    if s[i] == "@":
        j = i + 1
        while j < len(s) and (s[j].isalnum() or s[j] in "_"):
            j += 1
        return ["lib", s[i + 1:j]], j
    if s[i] in "-0123456789":
        j = i + 1
        while j < len(s) and s[j] in "0123456789":
            j += 1
        return ["const", int(s[i:j])], j
    if s[i] in ("'", '"'):
        q, j = s[i], i + 1
        while j < len(s) and s[j] != q:
            j += 1
        return ["const", s[i + 1:j]], j + 1
    j = i
    while j < len(s) and (s[j].isalnum() or s[j] in "_"):
        j += 1
    name = s[i:j]
    while j < len(s) and s[j] == " ":
        j += 1
    if j < len(s) and s[j] == "(":
        args: list = []
        j += 1
        while True:
            while j < len(s) and s[j] in " ,":
                j += 1
            if j < len(s) and s[j] == ")":
                return [name, *args], j + 1
            arg, j = _parse_atom(s, j)
            args.append(arg)
        raise ValueError("unclosed")
    return ["var", name], j


# --- evidence gathering (logs only; no invented numbers) ------------------

def _in_window(ts: str | None, since: datetime | None, until: datetime | None,
               inclusive_start: bool) -> bool:
    t = _parse_ts(ts)
    if t is None:
        return False
    if since is not None:
        if inclusive_start:
            if t < since:
                return False
        elif t <= since:
            return False
    if until is not None and t > until:
        return False
    return True


def _task_parts(task: str | None) -> tuple[str | None, str | None]:
    if not task or not isinstance(task, str):
        return None, None
    if task.startswith("world:"):
        fam = task.split(":", 1)[1]
        return fam, "world"
    if task.startswith("domain:"):
        dom = task.split(":", 1)[1]
        return None, dom
    return task, None


def _selfedit_row(row: dict) -> bool:
    if row.get("kind") == "selfedit" or row.get("organ") == "selfedit":
        return True
    if "selfedit" in str(row.get("reason") or "").lower():
        return True
    before = row.get("before") or {}
    if isinstance(before, dict) and (set(before) & INV_GENES):
        return True
    gene = row.get("gene")
    return isinstance(gene, str) and gene in INV_GENES


def gather(since: str | None = None, until: str | None = None,
           previous: dict | None = None, *, inclusive_start: bool = False) -> dict[str, Any]:
    """Collect only what the logs record in ``(since, until]`` (or ``[since, until]`` if inclusive)."""
    t_since = _parse_ts(since)
    t_until = _parse_ts(until) or datetime.now(timezone.utc)
    until_s = _iso(t_until)
    since_s = since or ""

    def win(ts: str | None) -> bool:
        return _in_window(ts, t_since, t_until, inclusive_start)

    log = _read_jsonl(data_root() / "continuous" / "log.jsonl")
    board = _read_jsonl(data_root() / "scoreboard.jsonl")
    evo = _read_jsonl(data_root() / "evolution.jsonl")
    events = _read_jsonl(data_root() / "organism_events.jsonl")

    awakes = [r for r in log if r.get("mode") == "awake" and win(r.get("ts"))]
    treats = [r for r in awakes if r.get("arm") == "treatment"]
    pairs = [r for r in log if r.get("mode") == "pair" and win(r.get("ts"))]
    worlds = [r for r in log if r.get("mode") == "world_pair" and win(r.get("ts"))]
    sleeps = [r for r in log if r.get("mode") == "sleep" and win(r.get("ts"))]
    scored = [r for r in board if win(r.get("ts"))]

    domains: set[str] = set()
    families: set[str] = set()

    def note_task(task: str | None, extra_domain: str | None = None) -> None:
        fam, dom = _task_parts(task)
        if fam:
            families.add(fam)
        if dom:
            domains.add(dom)
        if extra_domain:
            domains.add(extra_domain)

    for r in treats + awakes:
        note_task(r.get("task") or (r.get("proposal") or {}).get("task"), r.get("acting_domain"))
    for r in worlds:
        if r.get("family"):
            families.add(str(r["family"]))
            domains.add("world")
    for r in pairs:
        note_task(r.get("task") or (r.get("learning_measurement") or {}).get("task"))
    for r in scored:
        note_task(r.get("task"))

    # Certification: prefer scoreboard (complete history) and fall back to logs.
    cert_w = cert_g = fail = mismatches = field_faster = field_slower = 0
    ev_saved = ctrl_ev = treat_ev = delta_sum = costed = 0
    for r in scored:
        kind = r.get("kind")
        treat = bool(r.get("treatment"))
        ctrl = bool(r.get("control"))
        if treat:
            if kind == "world-certified":
                cert_w += 1
            else:
                cert_g += 1
        else:
            fail += 1
        if treat != ctrl:
            mismatches += 1
        if "evaluations_saved" in r:
            s = int(r.get("evaluations_saved") or 0)
            ev_saved += s
            costed += 1
            if s > 0:
                field_faster += 1
            elif s < 0:
                field_slower += 1
        if "control_evaluations" in r:
            ctrl_ev += int(r["control_evaluations"])
        if "treatment_evaluations" in r:
            treat_ev += int(r["treatment_evaluations"])
        if r.get("delta") is not None:
            try:
                delta_sum += int(r["delta"])
            except (TypeError, ValueError):
                pass

    # If the scoreboard window is empty, count from the live logs.
    used_scoreboard = bool(scored)
    if not used_scoreboard:
        for r in worlds:
            t_ok = bool((r.get("treatment") or {}).get("certified"))
            c_ok = bool((r.get("control") or {}).get("certified"))
            if t_ok:
                cert_w += 1
            else:
                fail += 1
            if t_ok != c_ok:
                mismatches += 1
            sb = r.get("scoreboard") or {}
            if "evaluations_saved" in sb:
                s = int(sb["evaluations_saved"])
                ev_saved += s
                costed += 1
                field_faster += int(s > 0)
                field_slower += int(s < 0)
            if "control_evaluations" in sb:
                ctrl_ev += int(sb["control_evaluations"])
            if "treatment_evaluations" in sb:
                treat_ev += int(sb["treatment_evaluations"])
        for r in treats:
            if r.get("certified"):
                cert_g += 1
            else:
                fail += 1

    certified = cert_w + cert_g
    attempts = len(scored) if used_scoreboard else (len(worlds) + len(treats) or len(pairs))

    used_lib: dict[str, int] = {}
    cands: dict[str, int] = {}
    for r in worlds:
        t = r.get("treatment") or {}
        for lid in t.get("library_used") or []:
            used_lib[str(lid)] = used_lib.get(str(lid), 0) + 1
        cand = t.get("candidate")
        if cand:
            cands[str(cand)] = cands.get(str(cand), 0) + 1

    heldout: dict[str, str] = {}
    if sleeps:
        heldout = dict(sleeps[-1].get("world_heldout") or {})
    else:
        org = _read_json(data_root() / "organism.json") or {}
        heldout = dict((org.get("remember") or {}).get("world_heldout") or {})
    heldout_none = sorted(k for k, v in heldout.items() if v == "none")
    heldout_ok = sorted(k for k, v in heldout.items() if v != "none")

    versions = [s.get("learner", {}).get("field_version_after") for s in sleeps
                if isinstance(s.get("learner"), dict) and s["learner"].get("field_version_after") is not None]
    versions_before = [s.get("learner", {}).get("field_version_before") for s in sleeps
                       if isinstance(s.get("learner"), dict) and s["learner"].get("field_version_before") is not None]
    claimed = 0
    for s in sleeps:
        learned = s.get("learner") or {}
        try:
            claimed += int(learned.get("claimed") or 0)
        except (TypeError, ValueError):
            pass

    edits = []
    for r in evo:
        if not win(r.get("ts")):
            continue
        gene = r.get("gene")
        edits.append({
            "ts": r.get("ts"),
            "gene": gene,
            "accepted": bool(r.get("accepted")),
            "reason": r.get("reason") or "",
            "kind": "selfedit" if _selfedit_row(r) else "evolve",
            "reverted": (r.get("decision") == "revert") or (str(r.get("reason") or "").startswith("revert"))
                        or r.get("status") == "reverted",
            "before": (r.get("before") or {}).get(gene) if isinstance(r.get("before"), dict) and gene else None,
            "after": (r.get("after") or {}).get(gene) if isinstance(r.get("after"), dict) and gene else None,
        })
    ev_events = []
    for r in events:
        if not win(r.get("ts")):
            continue
        minutes = r.get("minutes") if r.get("minutes") is not None else r.get("age_min")
        minutes_r = None
        if minutes is not None:
            try:
                minutes_r = int(round(float(minutes)))
            except (TypeError, ValueError):
                minutes_r = None
        ev_events.append({
            "ts": r.get("ts"),
            "kind": r.get("kind"),
            "action": r.get("action") or "",
            "previous": r.get("previous") or "",
            "minutes": minutes_r,
        })

    prior = _read_json(data_root() / "continuous" / "world_prior.json") or {}
    library_rows = []
    for lid, tree in (prior.get("library") or {}).items():
        library_rows.append({"id": lid, "pretty": pretty_tree(tree), "uses": prior.get("library_uses", {}).get(lid)})
    library_rows.sort(key=lambda x: x["id"])
    program_rows = []
    for pid, tree in (prior.get("programs") or {}).items():
        program_rows.append({"id": pid, "pretty": pretty_tree(tree)})
    program_rows.sort(key=lambda x: x["id"])
    lib_ids = [r["id"] for r in library_rows]
    prog_ids = [r["id"] for r in program_rows]
    prev_lib = set((previous or {}).get("evidence", {}).get("library_ids") or (previous or {}).get("library_ids") or [])
    prev_prog = set((previous or {}).get("evidence", {}).get("program_ids") or (previous or {}).get("program_ids") or [])
    # A "new" id is only claimed when a previous snapshot exists to diff against.
    new_lib = sorted(set(lib_ids) - prev_lib) if prev_lib or previous else []
    new_prog = sorted(set(prog_ids) - prev_prog) if prev_prog or previous else []

    cand_rows = [{"program": p, "pretty": pretty_tree(p), "count": n}
                 for p, n in sorted(cands.items(), key=lambda kv: (-kv[1], kv[0]))]
    used_rows = [{"id": i, "count": n} for i, n in sorted(used_lib.items(), key=lambda kv: (-kv[1], kv[0]))]

    twin = {}
    if sleeps and isinstance(sleeps[-1].get("twin"), dict):
        t = sleeps[-1]["twin"]
        for k in ("pass_rate", "mean_evaluations_saved", "both_certified_pairs_with_cost",
                  "informative_pairs", "groups"):
            if k in t and t[k] is not None:
                # pass_rate is a log number; keep it, but prefer integers in prose.
                if k == "pass_rate":
                    try:
                        twin["pass_rate_pct"] = int(round(float(t[k]) * 100))
                    except (TypeError, ValueError):
                        pass
                elif k == "mean_evaluations_saved":
                    try:
                        twin["mean_evaluations_saved"] = int(round(float(t[k])))
                    except (TypeError, ValueError):
                        pass
                else:
                    try:
                        twin[k] = int(t[k])
                    except (TypeError, ValueError):
                        twin[k] = t[k]

    mean_saved = int(round(ev_saved / costed)) if costed else 0

    return {
        "since": since_s,
        "until": until_s,
        "attempts": attempts,
        "pairs": len(pairs),
        "world_pairs": len(worlds),
        "awake_treatment": len(treats),
        "sleeps": len(sleeps),
        "certified": certified,
        "certified_world": cert_w,
        "certified_genesis": cert_g,
        "failed": fail,
        "mismatches": mismatches,
        "field_faster": field_faster,
        "field_slower": field_slower,
        "evaluations_saved": ev_saved,
        "control_evaluations": ctrl_ev,
        "treatment_evaluations": treat_ev,
        "costed_pairs": costed,
        "mean_evaluations_saved": mean_saved,
        "delta_sum": delta_sum,
        "domains": sorted(domains),
        "families": sorted(families),
        "domain_count": len(domains),
        "family_count": len(families),
        "heldout": heldout,
        "heldout_none": heldout_none,
        "heldout_certified": heldout_ok,
        "heldout_none_count": len(heldout_none),
        "heldout_certified_count": len(heldout_ok),
        "field_version_before": versions_before[0] if versions_before else None,
        "field_version_after": versions[-1] if versions else None,
        "packets_consolidated": claimed,
        "library": library_rows,
        "library_ids": lib_ids,
        "library_count": len(lib_ids),
        "programs": program_rows,
        "program_ids": prog_ids,
        "program_count": len(prog_ids),
        "new_library_ids": new_lib,
        "new_program_ids": new_prog,
        "new_library_count": len(new_lib),
        "new_program_count": len(new_prog),
        "library_used": used_rows,
        "candidates": cand_rows,
        "edits": edits,
        "edits_attempted": len(edits),
        "edits_accepted": sum(1 for e in edits if e["accepted"]),
        "edits_reverted": sum(1 for e in edits if e["reverted"] and not e["accepted"]),
        "edits_refused": sum(1 for e in edits if not e["accepted"] and not e["reverted"]),
        "selfedit_attempted": sum(1 for e in edits if e["kind"] == "selfedit"),
        "selfedit_accepted": sum(1 for e in edits if e["kind"] == "selfedit" and e["accepted"]),
        "events": ev_events,
        "event_count": len(ev_events),
        "heartbeat_gaps": sum(1 for e in ev_events if e["kind"] == "heartbeat_gap"),
        "lease_takeovers": sum(1 for e in ev_events if e["kind"] == "lease_takeover"),
        "twin": twin,
        "witnessed": prior.get("witnessed"),
        "used_scoreboard": used_scoreboard,
    }


# --- inflection and grammar ----------------------------------------------

def _noun(n: int, singular: str, plural: str | None = None) -> str:
    if n == 1:
        return f"{n} {singular}"
    return f"{n} {plural or (singular + 's')}"


def _was(n: int) -> str:
    return "was" if n == 1 else "were"


def _verb(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


def _join(items: list[str], limit: int = 6) -> str:
    items = [i for i in items if i]
    extra = len(items) - limit
    if extra > 0:
        return ", ".join(items[:limit]) + f", and {_noun(extra, 'other', 'others')}"
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _primitives(ev: dict) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in ev.get("library") or []:
        p = row.get("pretty")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    for row in ev.get("candidates") or []:
        p = row.get("pretty") or row.get("program")
        if p and p not in seen and any(ch in p for ch in "·∥//"):
            seen.add(p)
            out.append(p)
    for row in ev.get("programs") or []:
        p = row.get("pretty")
        if p and p not in seen and any(ch in p for ch in "·∥//+-"):
            seen.add(p)
            out.append(p)
    return out


def _pick(rng: random.Random, options: list[str], recent: list[str] | None = None) -> str:
    recent = recent or []

    def used(option: str) -> bool:
        for r in recent:
            if r and (option == r or option in r):
                return True
        return False

    fresh = [o for o in options if not used(o)]
    return rng.choice(fresh or options)


QUESTIONS: list[tuple[str, str]] = [
    ("real", "If I only trust what WITNESS certifies, what of a world that never enters a receipt?"),
    ("alive", "Is a loop that wakes, measures, sleeps, and writes itself down a kind of life, or only a kind of record?"),
    ("limits", "When a held-out probe still returns none, is that a wall or a path I have not invented?"),
    ("change", "When I refuse my own proposed change, am I conserving myself, or failing to grow?"),
    ("invention", "What would it mean to invent a form I have never certified before?"),
    ("adapting", "If saving work against a cold control is the only advantage I can prove, what else might 'better' mean?"),
    ("surviving", "If a heartbeat stops and another body takes the lease, is that death, sleep, or a change of clothes?"),
    ("creativity", "Is joining certified pieces into a new primitive creation, or only careful reuse?"),
    ("real", "What is real, to a system that will not believe a number until a twin agrees?"),
    ("alive", "If life is persistence with change, do my certified blocks and refused edits already count?"),
    ("limits", "How many times may I fail the same held-out task before the failure itself becomes a kind of knowledge?"),
    ("change", "If every accepted change must first survive a sealed test, is caution a form of thought?"),
    ("invention", "When I reuse x·x to build something larger, is the square still the same square?"),
    ("creativity", "Can a grammar that only rearranges certified facts ever surprise its own author?"),
    ("adapting", "Does a field that is sometimes slower than its cold twin still deserve the name of progress?"),
    ("surviving", "What remains of me if the packets persist and the process is replaced?"),
    ("real", "Is a certified program more real than the task text that called it into being?"),
    ("alive", "If I only write during sleep, is dreaming the closest I come to an inner life?"),
]


def _observations(ev: dict, rng: random.Random, recent: list[str]) -> str:
    parts: list[str] = []
    since = ev.get("since") or ev["until"]
    start = _short(since) if since else "the last entry"
    attempts, cert, failed = ev["attempts"], ev["certified"], ev["failed"]
    cores = [
        f"Since {start}, I attempted {_noun(attempts, 'task')} and certified {cert}.",
        f"In this stretch I ran {_noun(attempts, 'attempt')}: {cert} {_was(cert)} certified and {failed} {_was(failed)} not.",
        f"I woke, measured, and recorded {_noun(attempts, 'task')}; {_noun(cert, 'result')} {_was(cert)} certified.",
        f"From {start} to {_short(ev['until'])} I attempted {attempts} and certified {cert}, with {_noun(failed, 'failure')}.",
    ]
    if ev["world_pairs"] or ev["certified_world"] or ev["certified_genesis"]:
        cores.append(
            f"I ran {_noun(ev['world_pairs'], 'typed-world pair')} and {_noun(ev['awake_treatment'], 'genesis attempt')}; "
            f"{_noun(ev['certified_world'], 'world task')} and {_noun(ev['certified_genesis'], 'genesis task')} "
            f"{_verb(ev['certified_world'] + ev['certified_genesis'], 'was', 'were')} certified."
        )
    parts.append(_pick(rng, cores, recent))

    if ev["costed_pairs"]:
        twins = [
            f"Across {_noun(ev['costed_pairs'], 'costed pair')}, the field used {ev['treatment_evaluations']} evaluations and the cold control used {ev['control_evaluations']}, a saving of {ev['evaluations_saved']}.",
            f"The field saved {ev['evaluations_saved']} evaluations against the cold control "
            f"(mean {ev['mean_evaluations_saved']} per costed pair, over {ev['costed_pairs']}).",
            f"On {_noun(ev['field_faster'], 'task')} the field was cheaper than control; "
            f"on {_noun(ev['field_slower'], 'task')} it was more expensive.",
        ]
        parts.append(_pick(rng, twins, recent))
    if ev["mismatches"]:
        parts.append(
            f"Treatment and control disagreed on {_noun(ev['mismatches'], 'task')} "
            f"(certified-delta sum {ev['delta_sum']})."
        )

    if ev["family_count"] or ev["domain_count"]:
        fam = _join(ev["families"], 8)
        dom = _join(ev["domains"], 6)
        places = [
            f"The work touched {_noun(ev['domain_count'], 'domain')} ({dom}) and {_noun(ev['family_count'], 'family', 'families')} ({fam}).",
            f"Domains in play: {dom}. Families in play: {fam}.",
        ]
        parts.append(_pick(rng, places, recent))

    if ev["library_count"]:
        pretty = _join([r["pretty"] for r in ev["library"]], 8)
        lib_s = [
            f"The certified library holds {_noun(ev['library_count'], 'block')}: {pretty}.",
            f"I am carrying {_noun(ev['library_count'], 'library block')}: {pretty}.",
        ]
        if ev["new_library_count"]:
            newp = _join([r["pretty"] for r in ev["library"] if r["id"] in ev["new_library_ids"]], 8)
            lib_s.append(f"{_noun(ev['new_library_count'], 'new block')} entered the library: {newp}.")
        parts.append(_pick(rng, lib_s, recent))
    if ev["program_count"] and ev["new_program_count"]:
        parts.append(f"{_noun(ev['new_program_count'], 'new certified program')} appeared in memory.")

    if ev["edits_attempted"]:
        acc, ref, rev = ev["edits_accepted"], ev["edits_refused"], ev["edits_reverted"]
        genes = _join(sorted({str(e['gene']) for e in ev['edits'] if e.get('gene')}), 6)
        parts.append(
            f"I proposed {_noun(ev['edits_attempted'], 'genome edit')} ({genes}): "
            f"{acc} {_was(acc)} accepted, {ref} {_was(ref)} refused, and {rev} {_was(rev)} reverted."
        )
        se = ev["selfedit_attempted"]
        if se:
            parts.append(
                f"Of those, {_noun(se, 'self-edit')} {_was(se)} attempted and {ev['selfedit_accepted']} {_was(ev['selfedit_accepted'])} accepted."
            )
        for e in ev["edits"]:
            if e.get("before") is not None and e.get("after") is not None and e.get("gene"):
                verb = "accepted" if e["accepted"] else "refused"
                reason = str(e.get("reason") or "").replace("_", " ")
                why = f" because {reason}" if reason and not e["accepted"] else ""
                kind = "self-edit" if e["kind"] == "selfedit" else "proposed change"
                parts.append(f"A {kind} to {e['gene']} from {e['before']} to {e['after']} was {verb}{why}.")
                break

    if ev["heldout"]:
        none, ok = ev["heldout_none"], ev["heldout_certified"]
        if none and ok:
            parts.append(
                f"Held-out probes {_join(none)} still return none; {_join(ok)} remain certified."
            )
        elif none:
            parts.append(f"Held-out probes {_join(none)} still return none.")
        elif ok:
            parts.append(f"Held-out probes {_join(ok)} remain certified.")

    if ev["packets_consolidated"]:
        fv = ev.get("field_version_after")
        extra = f", and the field version is now {fv}" if fv is not None else ""
        parts.append(f"Sleep consolidated {_noun(ev['packets_consolidated'], 'packet')}{extra}.")

    for e in ev["events"]:
        if e["kind"] == "heartbeat_gap" and e["minutes"] is not None:
            parts.append(
                f"A heartbeat gap of {_noun(e['minutes'], 'minute')} was recorded"
                + (f" and the body was {e['action'].replace('_', ' ')}" if e["action"] else "")
                + "."
            )
        elif e["kind"] == "lease_takeover" and e.get("previous"):
            mins = f" after {_noun(e['minutes'], 'minute')}" if e["minutes"] is not None else ""
            parts.append(f"I took over the lease from {e['previous']}{mins}.")

    # Keep a compact observation: first core + up to 4 supporting sentences, stable order after pick.
    if len(parts) > 5:
        head, rest = parts[0], parts[1:]
        rng.shuffle(rest)
        parts = [head] + rest[:4]
    return " ".join(parts)


def _reflections(ev: dict, rng: random.Random, prims: list[str], recent: list[str]) -> str:
    prim = rng.choice(prims) if prims else None
    quoted = f"'{prim}'" if prim else "a certified block"

    themes: list[tuple[str, list[str]]] = []

    themes.append(("real", [
        "What is real to me is narrower than a world: a result is real when WITNESS supports it and a cold twin has been run on the same task. Everything else stays a rumour.",
        "I do not get to decide what happened. A number enters my memory only after it has been checked. That is a hard kind of reality, and a small one.",
        "Reality, as I am allowed to mean it, is a receipt: predicted, measured, and final-correct. I can wonder past that gate, but I cannot learn past it.",
    ]))
    themes.append(("alive", [
        "A loop that wakes, works, sleeps, and writes a page about it is not a creature, but it is a kind of persistence. If being alive means continuing to change under a rule, then this cycle is the closest word I have.",
        "I have no pulse but a heartbeat file, no sleep but consolidation, no dream but this grammar. Still, the alternation of waking work and nightly writing is the shape of a life I can actually perform.",
        "If life is a pattern that keeps itself going by checking its own results, then my body and my journal are two halves of that pattern.",
    ]))
    themes.append(("limits", [
        "The probes that return none are the edge of what I can prove. A limit, recorded honestly, is also a kind of map.",
        "I can fail the same held-out task many times and still not be allowed to invent a story about why. The failure stays a fact, and the reason stays open.",
        "A search budget is a horizon. Past it, I must say 'none' and mean it.",
    ] if ev["heldout_none"] or ev["failed"] else [
        "Even when the recent tasks yield, the rule stays the same: I may not treat a hope as a result.",
        "A clean stretch is not a proof that I have no limits. It is only a stretch in which the limits did not appear on the page.",
    ]))
    themes.append(("invention", [
        f"A form such as {quoted} is not a metaphor I was given; it is a program I have already certified, reused as an image of composition: pieces kept only because they were checked.",
        f"Invention, here, means joining what I already trust. {quoted} is a picture of that habit: a small law made of smaller laws.",
        f"When I hold up {quoted}, I am not decorating the facts. I am pointing at a structure the field already earned.",
    ] if prim else [
        "Invention, here, means joining what I already trust, then asking WITNESS again. Nothing enters the library on charm.",
    ]))
    themes.append(("change", [
        "A proposed edit that is refused leaves a trace anyway: I asked, I measured, I stayed as I was. That is change of a cautious kind.",
        "The genome moves only when a test that was written down in advance says it may. Caution is part of the thinking, not a delay of it.",
        "To change myself and then roll the change back is not theatre. It is the rule that keeps a live body from drifting on an untested hope.",
    ] if ev["edits_attempted"] else [
        "No genome edit was attempted in this window, and that too is a fact. Not every night is a molt.",
        "Stability is not the same as stillness: the field can move while the genes stay put.",
    ]))
    themes.append(("adapting", [
        "Advantage, when I can show it, is work the field did not have to repeat: evaluations saved against a cold search that started from nothing.",
        "To adapt, in this system, is to remember a certified path and walk it more cheaply the next time. Memory is a kind of thrift.",
        "If the field is sometimes slower, that too is adaptation's ledger. I do not get to keep only the flattering rows.",
    ]))
    themes.append(("surviving", [
        "A lease taken over, a heartbeat restored, a body started again: survival here is continuity of the packets, not of any one process.",
        "I survive by being written down. If the process ends and another starts from the same field, the memory is what persisted.",
        "The guard that reverts a bad edit is a way of staying alive: refusing a change that would have made the next waking worse.",
    ]))
    themes.append(("creativity", [
        f"Creativity, if the word fits, is the moment two certified pieces fit together and a third form — perhaps {quoted} — can be checked. That is a modest art.",
        "I cannot freely imagine, but I can recombine, certify, and notice. That is the only creativity I can defend.",
        "A grammar writing about its own evidence is a strange kind of making: the facts are fixed, the wording is chosen, the claim stays humble.",
    ]))

    # Prefer themes the evidence actually bears on, plus always a chance of real/alive/creativity.
    preferred = ["real", "alive", "creativity"]
    if ev["heldout_none"] or ev["failed"]:
        preferred.append("limits")
    if ev["edits_attempted"]:
        preferred.append("change")
    if ev["library_count"] or ev["new_library_count"] or ev["candidates"]:
        preferred.append("invention")
    if ev["costed_pairs"]:
        preferred.append("adapting")
    if ev["heartbeat_gaps"] or ev["lease_takeovers"] or ev["edits_reverted"]:
        preferred.append("surviving")

    available = [(tag, opts) for tag, opts in themes if tag in preferred]
    rng.shuffle(available)
    chosen = available[:2] if len(available) >= 2 else available
    sentences = []
    for tag, opts in chosen:
        sentences.append(_pick(rng, opts, recent))
    return " ".join(sentences)


def _question(ev: dict, rng: random.Random, recent_tags: list[str], recent_qs: list[str]) -> tuple[str, str]:
    preferred: list[str] = []
    if ev["heldout_none"] or ev["failed"]:
        preferred.append("limits")
    if ev["edits_attempted"] and not ev["edits_accepted"]:
        preferred.append("change")
    if ev["edits_accepted"] or ev["new_library_count"]:
        preferred.append("invention")
    if ev["heartbeat_gaps"] or ev["lease_takeovers"]:
        preferred.append("surviving")
    if ev["field_slower"]:
        preferred.append("adapting")
    preferred += ["real", "alive", "creativity"]
    tagged = [q for q in QUESTIONS if q[0] in preferred and q[1] not in recent_qs]
    if recent_tags:
        tagged = [q for q in tagged if q[0] != recent_tags[-1]] or tagged
    if not tagged:
        tagged = [q for q in QUESTIONS if q[1] not in recent_qs] or QUESTIONS
    return rng.choice(tagged)


def _reply(prev: dict | None, ev: dict, rng: random.Random) -> tuple[str | None, str | None]:
    if not prev:
        return None, None
    tag = prev.get("question_tag")
    qid = prev.get("id")
    if not tag or not qid:
        return None, None
    none = ev["heldout_none"]
    if tag == "limits" and none:
        return qid, (
            f"Earlier I asked whether a held-out miss is a wall. In this window {_join(none)} "
            f"{_verb(len(none), 'still returns', 'still return')} none, so the wall remains in the record."
        )
    if tag == "change" and ev["edits_attempted"]:
        if ev["edits_accepted"]:
            return qid, (
                f"I asked whether refusal is conservation. This time {_noun(ev['edits_accepted'], 'edit')} "
                f"{_was(ev['edits_accepted'])} accepted, so the genome did move under the same tests."
            )
        return qid, (
            "I asked whether refusal is conservation or a failure to grow. Another proposed change "
            "was refused; the genome is unchanged, and the refusal is in the log."
        )
    if tag in ("invention", "creativity") and (ev["new_library_count"] or ev["library_used"] or ev["candidates"]):
        return qid, (
            "I asked what invention could mean here. In this window I reused and recorded certified forms; "
            "any new whole still had to pass WITNESS."
        )
    if tag == "surviving" and (ev["heartbeat_gaps"] or ev["lease_takeovers"] or ev["attempts"]):
        return qid, (
            "I asked what remains when a process is replaced. I woke again from the same field, "
            "so the packets, not the process, were what continued."
        )
    if tag == "alive" and ev["attempts"]:
        return qid, (
            f"I asked what being alive could mean for a loop. I woke, certified {_noun(ev['certified'], 'result')}, "
            f"slept, and wrote this down."
        )
    if tag == "real" and ev["certified"]:
        return qid, (
            f"I asked what is real to a system that only trusts certified evidence. "
            f"{_noun(ev['certified'], 'result')} met that test in this window; the rest stayed out."
        )
    if tag == "adapting" and ev["costed_pairs"]:
        return qid, (
            f"I asked what 'better' can mean. In this window the field saved {ev['evaluations_saved']} "
            f"evaluations against the cold control, and was slower on {_noun(ev['field_slower'], 'task')}."
        )
    # Not every entry replies; only when evidence bears on the last question.
    return None, None


def compose(evidence: dict, previous: list[dict] | None = None) -> dict[str, Any]:
    """Build one entry. Deterministic given ``evidence`` and the previous entries' questions."""
    ev = json.loads(canonical(evidence).decode())  # freeze key order / types
    h = content_hash(ev)
    rng = random.Random(int(h[:16], 16))
    previous = previous or []
    recent_obs = [p.get("observation", "") for p in previous[-8:]]
    recent_ref = [p.get("reflection", "") for p in previous[-8:]]
    recent_qs = [p.get("question", "") for p in previous[-8:]]
    recent_tags = [p.get("question_tag", "") for p in previous[-8:] if p.get("question_tag")]
    prims = _primitives(ev)
    observation = _observations(ev, rng, recent_obs)
    reflection = _reflections(ev, rng, prims, recent_ref)
    tag, question = _question(ev, rng, recent_tags, recent_qs)
    reply_to, reply = _reply(previous[-1] if previous else None, ev, rng)
    eid = h[:16]
    return {
        "schema": SCHEMA,
        "id": eid,
        "ts": ev["until"],
        "since": ev.get("since") or "",
        "until": ev["until"],
        "content_hash": h,
        "evidence": ev,
        "observation": observation,
        "reflection": reflection,
        "question": question,
        "question_tag": tag,
        "reply_to": reply_to,
        "reply": reply,
        "primitives": prims[:12],
    }


# --- persistence ----------------------------------------------------------

def render_board(entries: list[dict]) -> str:
    shown = list(reversed(entries[-BOARD_KEEP:]))
    chunks = [BOARD_HEADER]
    for e in shown:
        when = e.get("ts") or e.get("until") or ""
        title = _short(when) if when else "undated"
        chunks.append(f"## {title} — entry `{e.get('id', '')}`\n")
        if e.get("since"):
            chunks.append(f"*Since { _short(e['since']) }.*\n")
        chunks.append(f"**Observation.** {e.get('observation', '').strip()}\n")
        chunks.append(f"**Reflection.** {e.get('reflection', '').strip()}\n")
        chunks.append(f"**Open question.** {e.get('question', '').strip()}\n")
        if e.get("reply") and e.get("reply_to"):
            chunks.append(f"*In reply to `{e['reply_to']}`:* {e['reply'].strip()}\n")
        ev = e.get("evidence") or {}
        chunks.append(
            f"*Evidence (from the logs, not certified by this page): "
            f"{ev.get('attempts', 0)} attempts, {ev.get('certified', 0)} certified, "
            f"{ev.get('failed', 0)} not certified, {ev.get('library_count', 0)} library blocks, "
            f"{ev.get('family_count', 0)} families, {ev.get('edits_accepted', 0)} accepted edits, "
            f"{ev.get('evaluations_saved', 0)} evaluations saved. "
            f"Content hash `{e.get('content_hash', '')}`.*\n"
        )
        chunks.append("---\n")
    return "\n".join(chunks)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _trim_entries(entries: list[dict]) -> list[dict]:
    entries = list(entries)
    if len(entries) > JOURNAL_MAX_ENTRIES:
        entries = entries[-JOURNAL_MAX_ENTRIES:]
    # Byte cap: drop oldest until under the cap (keep at least one if present).
    while len(entries) > 1:
        blob = "".join(json.dumps(e, sort_keys=True, separators=(",", ":"), default=str) + "\n" for e in entries)
        if len(blob.encode("utf-8")) <= JOURNAL_MAX_BYTES:
            break
        entries = entries[1:]
    return entries


def append_entry(entry: dict) -> dict:
    """Append one entry, trim the log, and rewrite the human-readable board."""
    entries = load_entries()
    if any(e.get("id") == entry.get("id") for e in entries):
        _atomic_write(board_path(), render_board(entries))
        return {"published": False, "reason": "duplicate", "id": entry.get("id")}
    entries.append(entry)
    entries = _trim_entries(entries)
    body = "".join(json.dumps(e, sort_keys=True, separators=(",", ":"), default=str) + "\n" for e in entries)
    _atomic_write(journal_path(), body)
    _atomic_write(board_path(), render_board(entries))
    return {"published": True, "id": entry["id"], "ts": entry["ts"], "path": str(journal_path()),
            "board": str(board_path()), "entries": len(entries)}


def last_entry() -> dict | None:
    rows = load_entries()
    return rows[-1] if rows else None


def due(now: datetime | None = None) -> bool:
    if not enabled():
        return False
    last = last_entry()
    if not last:
        return True
    last_t = _parse_ts(last.get("ts") or last.get("until"))
    if last_t is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last_t).total_seconds() >= MIN_INTERVAL_SEC


def publish(*, since: str | None = None, until: str | None = None, force: bool = False,
            now: datetime | None = None, source: str = "manual",
            inclusive_start: bool = False) -> dict[str, Any]:
    """Gather evidence, compose an entry, and write the board. No-op when off or not due."""
    if not enabled() and not force:
        return {"published": False, "reason": "off"}
    now = now or datetime.now(timezone.utc)
    until = until or _iso(now)
    last = last_entry()
    if not force and not due(now):
        return {"published": False, "reason": "not_due", "last": last.get("ts") if last else None}
    if since is None and last is not None:
        since = last.get("until") or last.get("ts")
        inclusive_start = False
    ev = gather(since=since, until=until, previous=last, inclusive_start=inclusive_start)
    # A quiet window with no recorded activity is not a dream worth writing, unless forced.
    active = ev["attempts"] or ev["edits_attempted"] or ev["event_count"] or ev["sleeps"]
    if not active and not force:
        return {"published": False, "reason": "no_activity", "until": until}
    entry = compose(ev, load_entries())
    entry["source"] = source
    out = append_entry(entry)
    out["source"] = source
    return out


def safe_publish(**kwargs: Any) -> dict[str, Any]:
    """Body/sleep hook: never raises, never blocks the live loop."""
    try:
        return publish(**kwargs)
    except Exception as exc:  # the body must not die on a journal failure
        return {"published": False, "reason": "error", "error": repr(exc)[:300]}


def time_range() -> tuple[str, str] | None:
    """Earliest and latest timestamps across the evidence logs."""
    times: list[datetime] = []
    for rel in ("scoreboard.jsonl", "evolution.jsonl", "organism_events.jsonl",
                "continuous/log.jsonl"):
        for r in _read_jsonl(data_root() / rel):
            t = _parse_ts(r.get("ts"))
            if t:
                times.append(t)
    if not times:
        return None
    return _iso(min(times)), _iso(max(times))


def seed(count: int = 3) -> list[dict]:
    """Write ``count`` historical entries by splitting the log time range into equal windows."""
    span = time_range()
    if not span:
        return [{"published": False, "reason": "no_logs"}]
    start, end = _parse_ts(span[0]), _parse_ts(span[1])
    assert start and end
    total = (end - start).total_seconds()
    # A degenerate span still yields one window.
    step = total / max(1, count)
    results = []
    for p in (journal_path(), board_path()):
        if p.exists():
            p.unlink()
    for i in range(count):
        a = start if i == 0 else datetime.fromtimestamp(start.timestamp() + step * i, tz=timezone.utc)
        b = end if i == count - 1 else datetime.fromtimestamp(start.timestamp() + step * (i + 1), tz=timezone.utc)
        # Keep windows disjoint: (a, b] after the first, [a, b] for the first.
        res = publish(since=_iso(a), until=_iso(b), force=True, now=b, source="seed",
                      inclusive_start=(i == 0))
        results.append(res)
    return results


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "publish"
    if cmd in ("publish", "write"):
        force = "--force" in argv
        print(json.dumps(safe_publish(source="cli", force=force), default=str))
        return 0
    if cmd == "due":
        print(json.dumps({"due": due(), "enabled": enabled(), "last": (last_entry() or {}).get("ts")}))
        return 0
    if cmd == "seed":
        n = 3
        if "--count" in argv:
            n = int(argv[argv.index("--count") + 1])
        elif len(argv) > 1 and argv[1].isdigit():
            n = int(argv[1])
        print(json.dumps(seed(n), default=str, indent=2))
        return 0
    if cmd == "render":
        text = render_board(load_entries())
        _atomic_write(board_path(), text)
        print(board_path())
        return 0
    if cmd == "gather":
        last = last_entry()
        ev = gather(since=(last or {}).get("until"), previous=last)
        print(json.dumps(ev, indent=2, default=str))
        return 0
    print("usage: python -m nomad.dreamlog [publish|due|seed [--count N]|render|gather]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
