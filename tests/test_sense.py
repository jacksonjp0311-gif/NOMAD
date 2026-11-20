"""SENSE: classify the task before search (nomad/sense.py).

Determinism and versioning, public-rows-only, honest domains (science only
from a tag), labels on families with known kinds, the off switch restoring
the exact prior behaviour, the cold control untouched, stage 1 unchanged,
no double charge, and the lead block reaching programs cold misses.
"""
from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

NEG = lambda x, y: y - y * (3 + y)            # noqa: E731  size 7, all outputs < 0
GROWTH = lambda x, y: (3 - y) * (y + y)       # noqa: E731  size 7, outgrows the inputs


def _int_task(tid, fn):
    from nomad.world_tasks import _int_task as mk
    return mk(tid, f"sense_{tid}", fn, 9)


def _key(s):
    return (s.tree, s.evaluations, s.reason, s.via)


class SenseRecordTests(unittest.TestCase):
    def test_record_is_deterministic_and_versioned(self) -> None:
        from nomad.sense import SCHEMA, sense
        from nomad.world_tasks import all_training
        for t in all_training():
            a, b = sense(t), sense(t)
            self.assertEqual(a, b)
            self.assertEqual(a["schema"], SCHEMA)
            self.assertEqual(len(a["sense_id"]), 16)
            for k in ("domain", "kind", "shape", "source", "features"):
                self.assertIn(k, a)

    def test_reads_public_rows_only(self) -> None:
        from nomad.sense import sense
        t = _int_task("pub", NEG)
        bent = replace(t, challenge=tuple((r, 999) for r, _ in t.challenge),
                       final=tuple((r, -999) for r, _ in t.final))
        self.assertEqual(sense(t), sense(bent))

    def test_domains_are_honest(self) -> None:
        from nomad.sense import KINDS, sense
        from nomad.world_tasks import all_training
        want = {"int": "mathematics", "genesis": "mathematics", "str": "language", "list": "coding"}
        for t in all_training():
            r = sense(t)
            self.assertEqual(r["domain"], want[t.opset])
            self.assertEqual(r["source"], "features")
            self.assertIn(r["kind"], KINDS[r["domain"]])
            self.assertNotEqual(r["domain"], "science")  # never guessed from features

    def test_tags_set_domain_and_kind(self) -> None:
        from nomad.sense import sense
        t = _int_task("tag", NEG)
        r = sense(t, tag={"domain": "science", "kind": "kinematics"})
        self.assertEqual((r["domain"], r["kind"], r["source"]), ("science", "kinematics", "tag"))
        self.assertIn("feature_kind", r["features"])
        self.assertEqual(sense(t, tag="astrology")["domain"], "other")
        self.assertEqual(sense(t, tag={"domain": "science"})["kind"], sense(t)["kind"])

    def test_generated_science_families_are_tagged(self) -> None:
        try:
            from nomad import science as SC
        except ImportError:
            self.skipTest("no science generator")
        import json
        p = ROOT / "data" / "deep" / "science_suite.json"
        if not p.exists():
            self.skipTest("no science suite")
        from nomad.sense import sense
        d = json.loads(p.read_text())
        for e in (d.get("easy") or [])[:4] + (d.get("hard") or [])[:4]:
            r = sense(SC.to_task(e))
            self.assertEqual(r["domain"], "science")
            self.assertEqual(r["kind"], SC.science_tag(e["family"])["kind"])

    def test_known_family_labels(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import sense_probe
        res = sense_probe.classifier()
        self.assertGreaterEqual(res["correct"], 18, res)

    def test_shapes_point_the_lead(self) -> None:
        from nomad.sense import lead_ops, sense
        self.assertEqual(sense(_int_task("n", NEG))["shape"], "negative")
        self.assertEqual(lead_ops(sense(_int_task("n", NEG))), ("sub",))
        self.assertEqual(lead_ops(sense(_int_task("g", GROWTH))), ("mul",))
        self.assertEqual(lead_ops(sense(_int_task("m", lambda x, y: max(x, y)))), ())  # selection
        from nomad.world_tasks import all_training
        for t in all_training():
            if t.opset in ("str", "list"):
                self.assertEqual(lead_ops(sense(t)), ())

    def test_sense_never_certifies_or_proposes(self) -> None:
        src = (ROOT / "nomad" / "sense.py").read_text()
        for word in ("certify", "Witness", "evaluate(", "run("):
            self.assertNotIn(word, src)
        r = __import__("nomad.sense", fromlist=["sense"]).sense(_int_task("np", NEG))
        self.assertNotIn("tree", r)
        self.assertNotIn("program", r)


class SenseSearchTests(unittest.TestCase):
    def test_lead_block_reaches_programs_cold_misses(self) -> None:
        from nomad.world import WorldPrior, evaluate
        for tid, fn, lead in (("neg", NEG, "sense:sub"), ("grow", GROWTH, "sense:mul")):
            t = _int_task(tid, fn)
            c, _ = evaluate(t, max_eval=10000)
            off, _ = evaluate(t, prior=WorldPrior(), max_eval=10000, sense=False)
            on, rec = evaluate(t, prior=WorldPrior(), max_eval=10000, sense=True)
            self.assertFalse(c.certified)
            self.assertFalse(off.certified)
            self.assertTrue(on.certified, on)
            self.assertEqual(on.via, lead)
            self.assertIsNotNone(rec)                    # WITNESS receipt, not the sense, certifies
            self.assertTrue(rec.supported)
            self.assertEqual(on.sense["shape"], "negative" if tid == "neg" else "growth")

    def test_off_switch_restores_prior_behaviour(self) -> None:
        from nomad.world import WorldPrior, synthesize
        tasks = [_int_task("o1", NEG), _int_task("o2", GROWTH)]
        from nomad.world_tasks import all_training
        tasks += all_training()
        for t in tasks:
            explicit = synthesize(t, prior=WorldPrior(), max_eval=10000, sense=False)
            with mock.patch.dict(os.environ, {"NOMAD_SENSE": "off"}):
                env = synthesize(t, prior=WorldPrior(), max_eval=10000)
            self.assertEqual(_key(explicit), _key(env))
            self.assertIsNone(env.sense)

    def test_cold_control_untouched(self) -> None:
        from nomad.world import synthesize
        for fn in (NEG, GROWTH):
            t = _int_task("c", fn)
            with mock.patch.dict(os.environ, {"NOMAD_SENSE": "off"}):
                a = synthesize(t, max_eval=10000)
            with mock.patch.dict(os.environ, {"NOMAD_SENSE": "on"}):
                b = synthesize(t, max_eval=10000)
            self.assertEqual(_key(a), _key(b))
            self.assertIsNone(b.sense)

    def test_stage1_unchanged_on_training_families(self) -> None:
        from nomad.world import WorldPrior, synthesize
        from nomad.world_tasks import all_training
        for t in all_training():
            off = synthesize(t, prior=WorldPrior(), max_eval=20000, sense=False)
            on = synthesize(t, prior=WorldPrior(), max_eval=20000, sense=True)
            self.assertEqual(_key(off), _key(on), t.family)

    def test_no_double_charge_over_the_whole_level(self) -> None:
        """Exhausting max_size with and without the lead block costs the same."""
        from nomad.world import WorldPrior, synthesize
        t = _int_task("big", lambda x, y: x ** 4 + 7 * y ** 3 + 11)   # growth; nothing fits at size 7
        off = synthesize(t, prior=WorldPrior(), max_eval=10**6, casesplit=False, sense=False)
        on = synthesize(t, prior=WorldPrior(), max_eval=10**6, casesplit=False, sense=True)
        self.assertEqual(on.sense["shape"], "growth")
        self.assertIsNone(off.tree)
        self.assertIsNone(on.tree)
        self.assertEqual(off.reason, "frontier")
        self.assertEqual(on.reason, "frontier")
        self.assertEqual(off.evaluations, on.evaluations)

    def test_brief_is_compact(self) -> None:
        from nomad.sense import brief, sense
        b = brief(sense(_int_task("b", NEG)))
        self.assertEqual(set(b), {"schema", "domain", "kind", "shape", "source", "sense_id"})
        self.assertIsNone(brief(None))


if __name__ == "__main__":
    unittest.main()
