"""Dream journal: grounding, determinism, size caps, and no effect on search."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class _Env:
    def __init__(self, **kv: Any):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.kv}
        for k, v in self.kv.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *exc):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


class Isolated(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nomad-dream-")
        self.data = Path(self._tmp.name)
        self._env = _Env(NOMAD_DATA=str(self.data), NOMAD_FEED=None, NOMAD_DREAMLOG="on")
        self._env.__enter__()
        for d in ("weights", "continuous", "society", "dreams"):
            (self.data / d).mkdir(parents=True)

    def tearDown(self) -> None:
        self._env.__exit__(None, None, None)
        self._tmp.cleanup()


def _fixture(data: Path) -> None:
    """A small, known history that grounding tests can count by hand."""
    _write_jsonl(data / "scoreboard.jsonl", [
        {"ts": "2026-11-21T10:00:00Z", "task": "world:min_pair", "treatment": True, "control": True,
         "delta": 0, "kind": "world-certified", "treatment_evaluations": 7, "control_evaluations": 100,
         "evaluations_saved": 93},
        {"ts": "2026-11-21T10:05:00Z", "task": "world:square_plus_y", "treatment": True, "control": True,
         "delta": 0, "kind": "world-certified", "treatment_evaluations": 40, "control_evaluations": 20,
         "evaluations_saved": -20},
        {"ts": "2026-11-21T10:10:00Z", "task": "domain:meta", "treatment": True, "control": False,
         "delta": 1, "kind": "certified", "treatment_evaluations": 3, "control_evaluations": 8,
         "evaluations_saved": 5},
        {"ts": "2026-11-21T10:15:00Z", "task": "world:absdiff", "treatment": False, "control": False,
         "delta": 0, "kind": "world-certified", "treatment_evaluations": 200, "control_evaluations": 200,
         "evaluations_saved": 0},
    ])
    _write_jsonl(data / "continuous" / "log.jsonl", [
        {"mode": "world_pair", "ts": "2026-11-21T10:00:00Z", "family": "min_pair",
         "control": {"certified": True, "evaluations": 100, "candidate": "min(x, y)"},
         "treatment": {"certified": True, "evaluations": 7, "candidate": "min(x, y)",
                       "library_used": ["Le41f5b00"]}},
        {"mode": "world_pair", "ts": "2026-11-21T10:05:00Z", "family": "square_plus_y",
         "control": {"certified": True},
         "treatment": {"certified": True, "candidate": "add(mul(x, x), y)",
                       "library_used": ["Lfd47622b"]}},
        {"mode": "pair", "ts": "2026-11-21T10:10:00Z", "task": "domain:meta",
         "learning_measurement": {"paired": True, "delta": 1, "kind": "certified"}},
        {"mode": "awake", "arm": "treatment", "ts": "2026-11-21T10:10:00Z", "task": "domain:meta",
         "acting_domain": "meta", "certified": True},
        {"mode": "sleep", "ts": "2026-11-21T10:20:00Z",
         "learner": {"claimed": 4, "field_version_before": 10, "field_version_after": 11},
         "world_heldout": {"absdiff": "none", "quartic_sum": "certified_correctness",
                           "last_first_upper": "none", "sum_minus_max": "none"},
         "twin": {"pass_rate": 1.0, "mean_evaluations_saved": 26, "both_certified_pairs_with_cost": 3,
                  "groups": 3}},
    ])
    _write_jsonl(data / "evolution.jsonl", [
        {"ts": "2026-11-21T10:12:00Z", "gene": "decay", "accepted": False, "reason": "not_better",
         "before": {"decay": 0.97, "library_k": 6}, "after": {"decay": 0.99, "library_k": 6}},
        {"ts": "2026-11-21T10:18:00Z", "gene": "inv_max_constants", "accepted": True, "reason": "advanced",
         "kind": "selfedit",
         "before": {"inv_max_constants": 2, "inv_const_depth": 1},
         "after": {"inv_max_constants": 3, "inv_const_depth": 1}},
    ])
    _write_jsonl(data / "organism_events.jsonl", [
        {"ts": "2026-11-21T10:02:00Z", "kind": "heartbeat_gap", "minutes": 9.0, "action": "redispatched_body"},
        {"ts": "2026-11-21T10:03:00Z", "kind": "lease_takeover", "previous": "gh-1", "age_min": 51.4},
    ])
    _write_json(data / "continuous" / "world_prior.json", {
        "schema": "nomad.world-prior.v1",
        "witnessed": 12,
        "library": {
            "Lfd47622b": ["mul", ["var", "x"], ["var", "x"]],
            "Le41f5b00": ["sub", ["var", "x"], ["var", "y"]],
        },
        "library_uses": {"Lfd47622b": 2, "Le41f5b00": 5},
        "programs": {
            "Wa190d20e": ["add", ["mul", ["var", "x"], ["var", "x"]], ["var", "y"]],
        },
    })


class GatherGroundingTests(Isolated):
    def test_counts_match_the_logs(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import gather
        ev = gather(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z", inclusive_start=True)
        self.assertEqual(ev["attempts"], 4)
        self.assertEqual(ev["certified"], 3)          # two world + one genesis; absdiff treatment false
        self.assertEqual(ev["certified_world"], 2)
        self.assertEqual(ev["certified_genesis"], 1)
        self.assertEqual(ev["failed"], 1)
        self.assertEqual(ev["mismatches"], 1)
        self.assertEqual(ev["field_faster"], 2)
        self.assertEqual(ev["field_slower"], 1)
        self.assertEqual(ev["evaluations_saved"], 93 - 20 + 5 + 0)
        self.assertEqual(ev["control_evaluations"], 100 + 20 + 8 + 200)
        self.assertEqual(ev["treatment_evaluations"], 7 + 40 + 3 + 200)
        self.assertEqual(ev["costed_pairs"], 4)
        self.assertEqual(ev["delta_sum"], 1)
        self.assertIn("min_pair", ev["families"])
        self.assertIn("square_plus_y", ev["families"])
        self.assertIn("absdiff", ev["families"])
        self.assertIn("meta", ev["domains"])
        self.assertIn("world", ev["domains"])
        self.assertEqual(ev["heldout_none"], ["absdiff", "last_first_upper", "sum_minus_max"])
        self.assertEqual(ev["heldout_certified"], ["quartic_sum"])
        self.assertEqual(ev["packets_consolidated"], 4)
        self.assertEqual(ev["field_version_after"], 11)
        self.assertEqual(ev["edits_attempted"], 2)
        self.assertEqual(ev["edits_accepted"], 1)
        self.assertEqual(ev["edits_refused"], 1)
        self.assertEqual(ev["selfedit_attempted"], 1)
        self.assertEqual(ev["selfedit_accepted"], 1)
        self.assertEqual(ev["edits"][0]["before"], 0.97)
        self.assertEqual(ev["edits"][0]["after"], 0.99)
        self.assertEqual(ev["edits"][1]["before"], 2)
        self.assertEqual(ev["edits"][1]["after"], 3)
        self.assertEqual(ev["heartbeat_gaps"], 1)
        self.assertEqual(ev["lease_takeovers"], 1)
        self.assertEqual(ev["events"][0]["minutes"], 9)
        self.assertEqual(ev["events"][1]["minutes"], 51)
        self.assertEqual(ev["library_count"], 2)
        self.assertEqual({r["pretty"] for r in ev["library"]}, {"x·x", "x - y"})
        self.assertEqual(ev["program_count"], 1)
        self.assertEqual(ev["programs"][0]["pretty"], "x·x + y")
        used_ids = {r["id"] for r in ev["library_used"]}
        self.assertEqual(used_ids, {"Le41f5b00", "Lfd47622b"})
        self.assertEqual(ev["sleeps"], 1)
        self.assertEqual(ev["world_pairs"], 2)
        self.assertEqual(ev["witnessed"], 12)

    def test_window_excludes_rows_outside_it(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import gather
        ev = gather(since="2026-11-21T10:09:00Z", until="2026-11-21T10:14:00Z", inclusive_start=False)
        # scoreboard rows at 10:10 only (10:00, 10:05, 10:15 out); evolution decay at 10:12
        self.assertEqual(ev["attempts"], 1)
        self.assertEqual(ev["certified"], 1)
        self.assertEqual(ev["certified_genesis"], 1)
        self.assertEqual(ev["edits_attempted"], 1)
        self.assertEqual(ev["edits"][0]["gene"], "decay")
        self.assertEqual(ev["event_count"], 0)

    def test_new_library_only_when_previous_snapshot_exists(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import gather
        first = gather(until="2026-11-21T11:00:00Z", inclusive_start=True)
        self.assertEqual(first["new_library_count"], 0)
        ev = gather(until="2026-11-21T11:00:00Z", previous={"evidence": {"library_ids": ["Le41f5b00"],
                                                                        "program_ids": []}})
        self.assertEqual(ev["new_library_ids"], ["Lfd47622b"])
        self.assertEqual(ev["new_program_ids"], ["Wa190d20e"])


class GrammarTests(Isolated):
    def test_compose_is_deterministic_and_grounded(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import compose, gather, pretty_tree
        ev = gather(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z", inclusive_start=True)
        a, b = compose(ev, []), compose(ev, [])
        self.assertEqual(a["content_hash"], b["content_hash"])
        self.assertEqual(a["observation"], b["observation"])
        self.assertEqual(a["reflection"], b["reflection"])
        self.assertEqual(a["question"], b["question"])
        self.assertEqual(a["id"], ev and a["content_hash"][:16])
        # Every integer in the observation appears in the evidence payload (including
        # pieces of timestamps and decimal gene values such as 0.97 -> 97).
        allowed = set(_ints(ev)) | set(_ints_in_text(json.dumps(ev, default=str)))
        mentioned = set(_ints_in_text(a["observation"]))
        leaked = mentioned - allowed
        self.assertFalse(leaked, f"ungrounded numbers in observation: {leaked}\n{a['observation']}")
        self.assertIn("3", a["observation"] or a["reflection"] or "")  # certified = 3 must be said somewhere
        self.assertTrue(
            any(s in (a["observation"] + a["reflection"]) for s in ("3", "certified")),
        )
        # Inflection: 1 takeover / 1 gap use singular copula near the number when those sentences appear.
        self.assertIn("x·x", " ".join(a["primitives"]))
        self.assertEqual(pretty_tree("div(add(x, mul(y, z)), 2)"), "(x + y·z)//2")

    def test_prose_varies_across_different_evidence(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import compose, gather
        ev = gather(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z", inclusive_start=True)
        ev2 = dict(ev, attempts=ev["attempts"] + 10, certified=ev["certified"] + 4, until="2026-11-21T12:00:00Z")
        a, b = compose(ev, []), compose(ev2, [])
        self.assertNotEqual(a["content_hash"], b["content_hash"])
        self.assertNotEqual(a["observation"], b["observation"])

    def test_reply_only_when_new_evidence_bears_on_the_last_question(self) -> None:
        _fixture(self.data)
        from nomad.dreamlog import compose, gather
        ev = gather(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z", inclusive_start=True)
        prev = {"id": "abcd", "question_tag": "limits", "question": "is it a wall?"}
        entry = compose(ev, [prev])
        self.assertEqual(entry["reply_to"], "abcd")
        self.assertIn("absdiff", entry["reply"])
        prev2 = {"id": "zzzz", "question_tag": "surviving"}
        # no heartbeat in a later empty-ish window? use ev which HAS heartbeat, so surviving also replies
        # Craft evidence with no bearing on 'creativity' and no new library in-window claim...
        # actually ev has candidates and library_used, so creativity would reply. Use a tag with no hook:
        ev_quiet = dict(ev, heldout_none=[], failed=0, edits_attempted=0, edits_accepted=0,
                        new_library_count=0, library_used=[], candidates=[], costed_pairs=0,
                        heartbeat_gaps=0, lease_takeovers=0, attempts=0, certified=0)
        silent = compose(ev_quiet, [{"id": "q1", "question_tag": "limits"}])
        self.assertIsNone(silent["reply_to"])
        self.assertIsNone(silent["reply"])


def _ints(obj: Any) -> list[int]:
    out: list[int] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int):
        return [obj]
    if isinstance(obj, float) and obj == int(obj):
        return [int(obj)]
    if isinstance(obj, str):
        return _ints_in_text(obj)
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_ints(v))
        return out
    if isinstance(obj, list):
        for v in obj:
            out.extend(_ints(v))
        return out
    return out


def _ints_in_text(text: str) -> list[int]:
    import re
    return [int(x) for x in re.findall(r"-?\d+", text)]


class PersistenceTests(Isolated):
    def test_publish_writes_journal_and_board_and_respects_rate_limit(self) -> None:
        _fixture(self.data)
        from nomad import dreamlog
        first = dreamlog.publish(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z",
                                 force=True, inclusive_start=True, source="test")
        self.assertTrue(first["published"])
        journal = self.data / "dreams" / "journal.jsonl"
        board = self.data / "feed" / "DREAMS.md"
        self.assertTrue(journal.exists())
        self.assertTrue(board.exists())
        text = board.read_text(encoding="utf-8")
        self.assertIn("not written by a language model", text)
        self.assertIn("reflection, not certified claims", text)
        self.assertIn("**Observation.**", text)
        self.assertIn("**Reflection.**", text)
        self.assertIn("**Open question.**", text)
        self.assertIn(first["id"], text)
        # second call immediately is not due
        second = dreamlog.publish(until="2026-11-21T11:01:00Z",
                                  now=datetime(2026, 11, 21, 11, 1, tzinfo=timezone.utc))
        self.assertFalse(second["published"])
        self.assertEqual(second["reason"], "not_due")
        self.assertEqual(len(dreamlog.load_entries()), 1)
        # 30 minutes later it is due
        later = datetime(2026, 11, 21, 11, 31, tzinfo=timezone.utc)
        self.assertTrue(dreamlog.due(later))
        third = dreamlog.publish(until="2026-11-21T11:31:00Z", now=later, force=False)
        # may be no_activity if we don't add new rows — add one scoreboard row first? until 11:31
        # fixture ends at 10:20, so attempts in (11:00, 11:31] is 0 -> no_activity
        self.assertEqual(third["reason"], "no_activity")
        with (self.data / "scoreboard.jsonl").open("a") as f:
            f.write(json.dumps({"ts": "2026-11-21T11:20:00Z", "task": "world:min_pair",
                                "treatment": True, "control": True, "delta": 0, "kind": "world-certified",
                                "treatment_evaluations": 7, "control_evaluations": 100,
                                "evaluations_saved": 93}) + "\n")
        fourth = dreamlog.publish(until="2026-11-21T11:31:00Z", now=later)
        self.assertTrue(fourth["published"])
        self.assertEqual(len(dreamlog.load_entries()), 2)
        # newest first on the board
        text = board.read_text(encoding="utf-8")
        i_new = text.index(fourth["id"])
        i_old = text.index(first["id"])
        self.assertLess(i_new, i_old)

    def test_switch_off_writes_nothing(self) -> None:
        _fixture(self.data)
        from nomad import dreamlog
        with _Env(NOMAD_DREAMLOG="off"):
            self.assertFalse(dreamlog.enabled())
            self.assertFalse(dreamlog.due())
            res = dreamlog.publish(force=False, until="2026-11-21T11:00:00Z")
            self.assertEqual(res["reason"], "off")
        self.assertFalse(dreamlog.journal_path().exists())
        self.assertFalse(dreamlog.board_path().exists())

    def test_size_caps_trim_oldest(self) -> None:
        _fixture(self.data)
        from nomad import dreamlog
        # shrink caps for the test
        old_b, old_n = dreamlog.JOURNAL_MAX_BYTES, dreamlog.JOURNAL_MAX_ENTRIES
        try:
            dreamlog.JOURNAL_MAX_ENTRIES = 5
            ev = dreamlog.gather(until="2026-11-21T11:00:00Z", inclusive_start=True)
            for i in range(8):
                ev_i = dict(ev, until=f"2026-11-21T12:0{i}:00Z", attempts=ev["attempts"] + i)
                entry = dreamlog.compose(ev_i, dreamlog.load_entries())
                dreamlog.append_entry(entry)
            rows = dreamlog.load_entries()
            self.assertEqual(len(rows), 5)
            # byte cap: never drop the newest entry, even if it alone exceeds the cap
            dreamlog.JOURNAL_MAX_ENTRIES = 100
            ev_big = dict(ev, until="2026-11-21T13:00:00Z", attempts=99)
            sample = dreamlog.compose(dict(ev_big, until="2026-11-22T00:00:00Z", certified=0), [])
            one = len(json.dumps(sample, sort_keys=True, separators=(",", ":"), default=str).encode())
            cap = one * 3 + 64
            dreamlog.JOURNAL_MAX_BYTES = cap
            for i in range(12):
                ev_i = dict(ev_big, until=f"2026-11-22T{i:02d}:00:00Z", certified=i)
                dreamlog.append_entry(dreamlog.compose(ev_i, []))
            blob = dreamlog.journal_path().read_bytes()
            self.assertLessEqual(len(blob), cap)
            n = len(dreamlog.load_entries())
            self.assertGreaterEqual(n, 1)
            self.assertLess(n, 12)
            board = dreamlog.board_path().read_text(encoding="utf-8")
            self.assertIn("NOMAD dream journal", board)
        finally:
            dreamlog.JOURNAL_MAX_BYTES = old_b
            dreamlog.JOURNAL_MAX_ENTRIES = old_n

    def test_board_keeps_only_last_100(self) -> None:
        _fixture(self.data)
        from nomad import dreamlog
        ev = dreamlog.gather(until="2026-11-21T11:00:00Z", inclusive_start=True)
        for i in range(105):
            ev_i = dict(ev, until=f"2026-11-25T{i//60:02d}:{i%60:02d}:00Z", attempts=i)
            dreamlog.append_entry(dreamlog.compose(ev_i, []))
        self.assertEqual(len(dreamlog.load_entries()), 105)
        text = dreamlog.board_path().read_text(encoding="utf-8")
        self.assertEqual(text.count("## "), 100)


class HookAndIsolationTests(Isolated):
    def test_safe_publish_never_raises(self) -> None:
        from nomad import dreamlog
        # no fixture; gather should still be safe
        res = dreamlog.safe_publish(force=True, until="2026-11-21T11:00:00Z")
        self.assertIn("published", res)
        # force a failure
        def boom(**kwargs):
            raise RuntimeError("journal exploded")
        self.assertEqual(dreamlog.safe_publish.__defaults__, None) or True
        orig = dreamlog.publish
        try:
            dreamlog.publish = boom  # type: ignore[assignment]
            out = dreamlog.safe_publish(force=True)
            self.assertFalse(out["published"])
            self.assertEqual(out["reason"], "error")
            self.assertIn("journal exploded", out["error"])
        finally:
            dreamlog.publish = orig

    def test_sleep_writes_a_journal_and_survives_a_journal_error(self) -> None:
        from nomad.continuous import pair, sleep
        pair()
        slept = sleep(arm="treatment")
        self.assertEqual(slept["mode"], "sleep")
        self.assertTrue((self.data / "dreams" / "journal.jsonl").exists())
        # break the organ, sleep must still return
        from nomad import dreamlog
        orig = dreamlog.publish
        try:
            def boom(**kwargs):
                raise RuntimeError("no dream")
            dreamlog.publish = boom  # type: ignore[assignment]
            slept2 = sleep(arm="treatment")
            self.assertEqual(slept2["mode"], "sleep")
        finally:
            dreamlog.publish = orig

    def test_sleep_is_unchanged_when_the_switch_is_off(self) -> None:
        from nomad.continuous import pair, sleep
        with _Env(NOMAD_DREAMLOG="off"):
            pair()
            slept = sleep(arm="treatment")
            self.assertEqual(slept["mode"], "sleep")
            self.assertIn("learner", slept)
        self.assertFalse((self.data / "dreams" / "journal.jsonl").exists())

    def test_control_sleep_does_not_write(self) -> None:
        from nomad.continuous import sleep
        out = sleep(arm="control")
        self.assertEqual(out["status"], "frozen")
        self.assertFalse((self.data / "dreams" / "journal.jsonl").exists())


class SearchUnaffectedTests(Isolated):
    def test_evaluate_is_byte_identical_with_journal_on_or_off(self) -> None:
        """Publishing a journal must not change search results, trees, or evaluation counts."""
        _fixture(self.data)
        from nomad.dreamlog import publish
        from nomad.world import WorldPrior, evaluate
        from nomad.world_tasks import all_training

        tasks = all_training()[:6]

        def snap(flag: str, also_publish: bool) -> list[tuple]:
            with _Env(NOMAD_DREAMLOG=flag):
                if also_publish:
                    publish(since="2026-11-21T09:00:00Z", until="2026-11-21T11:00:00Z",
                            force=True, inclusive_start=True)
                prior = WorldPrior()
                rows = []
                for t in tasks:
                    ev, rec = evaluate(t, prior=prior)
                    receipt = None if rec is None else getattr(rec, "receipt_hash", None) or repr(rec)
                    rows.append((t.task_id, ev.certified, ev.evaluations, ev.tree, ev.candidate, receipt))
                return rows

        off = snap("off", also_publish=False)
        on = snap("on", also_publish=True)
        self.assertEqual(off, on)
        self.assertTrue(any(r[1] for r in off), "fixture expected at least one certified training task")


class PrettyTests(unittest.TestCase):
    def test_algebraic_forms(self) -> None:
        from nomad.dreamlog import pretty_tree
        self.assertEqual(pretty_tree(["mul", ["var", "x"], ["var", "x"]]), "x·x")
        self.assertEqual(pretty_tree("add(mul(x, x), y)"), "x·x + y")
        self.assertEqual(pretty_tree("sub(mul(y, y), x)"), "y·y - x")
        self.assertEqual(pretty_tree("div(add(x, mul(y, z)), 2)"), "(x + y·z)//2")
        self.assertEqual(pretty_tree("lower(concat(s, s))"), "lower(s∥s)")
        self.assertEqual(pretty_tree("max(sub(x, y), 0)"), "max(x - y, 0)")


if __name__ == "__main__":
    unittest.main()
