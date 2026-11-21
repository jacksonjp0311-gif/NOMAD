"""SELFEDIT (docs/SELFEDIT.md): the self-edit sandbox and the tunable invention genes.

Default genome + switch on == switch off (exact); the sandbox never writes the live field; one bounded
gene per step; the floor-division fit and the constant closure are memory-only (an empty field gains
nothing); the sealed catalogue's ground truth matches its reference trees."""
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from nomad import genome as G  # noqa: E402
from nomad import invent as I  # noqa: E402
from nomad import selfedit as S  # noqa: E402
from nomad import selfedit_tasks as ST  # noqa: E402
from nomad.world import WorldPrior, run  # noqa: E402

C = lambda k: ["const", k]  # noqa: E731


class _Env:
    def __init__(self, **kv):
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


class Genes(unittest.TestCase):
    def test_defaults_reproduce_invent_round2(self):
        self.assertEqual(G.DEFAULTS["inv_max_constants"], I.MAX_CONSTANTS)
        self.assertEqual(G.DEFAULTS["inv_rounds"], I.ROUNDS)
        self.assertEqual(G.DEFAULTS["inv_const_depth"], 1)
        self.assertEqual(G.DEFAULTS["inv_floor_fit"], 0)
        for g in G.INVENT_GENES:
            lo, hi = G.BOUNDS[g]
            self.assertTrue(lo <= G.DEFAULTS[g] <= hi)

    def test_switch_off_ignores_genome(self):
        with _Env(NOMAD_SELFEDIT="off"), G.override({"inv_max_constants": 7, "inv_floor_fit": 1}):
            self.assertEqual(I.max_constants(), I.MAX_CONSTANTS)
            self.assertFalse(I.floor_fit())
        with _Env(NOMAD_SELFEDIT="on"), G.override({"inv_max_constants": 7, "inv_floor_fit": 1}):
            self.assertEqual(I.max_constants(), 7)
            self.assertTrue(I.floor_fit())
        self.assertEqual(G.OVERRIDE, {})

    def test_override_is_clamped(self):
        with G.override({"inv_max_constants": 99, "inv_const_depth": -3}):
            g = G.load()
        self.assertEqual(g["inv_max_constants"], G.BOUNDS["inv_max_constants"][1])
        self.assertEqual(g["inv_const_depth"], 1)

    def test_genome_path_env(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.json"
            p.write_text(json.dumps({"genes": {"inv_floor_fit": 1}}))
            with _Env(NOMAD_GENOME=str(p)):
                self.assertEqual(G.load()["inv_floor_fit"], 1)


class Constants(unittest.TestCase):
    scales = [(2, C(2)), (3, C(3))]

    def test_depth1_unchanged(self):
        with _Env(NOMAD_SELFEDIT="off"):
            self.assertEqual([k for k, _ in I.constants(self.scales)], [4, 6][:I.MAX_CONSTANTS])
        with _Env(NOMAD_SELFEDIT="on"), G.override(dict(G.DEFAULTS)):
            self.assertEqual([k for k, _ in I.constants(self.scales)], [4, 6])

    def test_depth2_closure(self):
        with _Env(NOMAD_SELFEDIT="on"), G.override({"inv_const_depth": 2, "inv_max_constants": 8}):
            got = dict(I.constants(self.scales, for_floor=True))
            self.assertEqual([k for k, _ in I.constants(self.scales)], [4, 6])   # targets: never the genes
        self.assertEqual(sorted(got), [4, 6, 8, 9, 12, 16, 18, 24])   # 8 smallest of the depth-2 closure
        for k in got:
            self.assertIn(k, got)
            self.assertEqual(run(got[k], {}), k)
        with _Env(NOMAD_SELFEDIT="on"), G.override({"inv_const_depth": 2, "inv_max_constants": 2}):
            self.assertEqual([k for k, _ in I.constants(self.scales, for_floor=True)], [4, 6])   # cap, smallest first

    def test_empty_field_has_no_constants(self):
        with _Env(NOMAD_SELFEDIT="on"), G.override({"inv_const_depth": 2, "inv_max_constants": 8}):
            self.assertEqual(I.constants([], for_floor=True), [])


class Propose(unittest.TestCase):
    def test_one_bounded_gene(self):
        cur = dict(G.DEFAULTS)
        for seed in range(40):
            cand, gene = S.propose(cur, seed)
            self.assertIn(gene, G.INVENT_GENES)
            diff = [k for k in cur if cand[k] != cur[k]]
            self.assertEqual(diff, [gene])
            lo, hi = G.BOUNDS[gene]
            self.assertTrue(lo <= cand[gene] <= hi)
            self.assertEqual(S.propose(cur, seed), (cand, gene))


    def test_tabu(self):
        cur = dict(G.DEFAULTS)
        first, _g = S.propose(cur, 5)
        again, _g2 = S.propose(cur, 5, {S._key(first)})
        self.assertNotEqual(S._key(again), S._key(first))
        hist = [{"organ": "selfedit", "accepted": False, "reason": "dev_not_better", "before": cur, "after": first}]
        self.assertEqual(S.tabu_from_log(cur, hist), {S._key(first)})
        self.assertEqual(S.tabu_from_log(first, hist), set())


class Sandbox(unittest.TestCase):
    def test_window_from_rows(self):
        rows = [{"ts": "2026-11-21T10:00:00Z", "task": "world:rev_upper", "treatment": True, "treatment_evaluations": 9},
                {"ts": "2026-11-21T09:00:00Z", "task": "world:rev_upper", "treatment": False},
                {"ts": "2026-11-21T10:01:00Z", "task": "domain:meta", "treatment": True}]
        w = S.window("2026-11-21T09:30:00Z", rows)
        self.assertEqual(w["pairs"], 1)
        self.assertEqual(w["families"], ["rev_upper"])
        self.assertEqual(w["recorded"], {"rev_upper": [True, 9]})

    def test_losses(self):
        self.assertEqual(S.losses({"a": [True, 5], "b": [False, 10]}, {"a": [True, 6], "b": [True, 3]}), ["a"])
        self.assertEqual(S.losses({"a": [True, 5]}, {"a": [False, 10000]}), ["a"])

    def test_no_change_rejected(self):
        row = S.step(dict(G.DEFAULTS), 1, dev_field=(WorldPrior(), None), dev=[], keep=[], tests=False)
        self.assertFalse(row["accepted"])
        self.assertEqual(row["reason"], "dev_not_better")

    def test_attempt_never_writes_live_field(self):
        dev = S.dev_tasks()[:3]
        keep = S.keep_tasks()[:2]
        with tempfile.TemporaryDirectory() as d, _Env(NOMAD_DATA=d, NOMAD_SELFEDIT="on", NOMAD_GENOME=None):
            (Path(d) / "continuous").mkdir()
            (Path(d) / "continuous" / "world_prior.json").write_text(json.dumps(WorldPrior().snapshot()))
            old_dev, old_keep = S.dev_tasks, S.keep_tasks
            S.dev_tasks, S.keep_tasks = (lambda seed=7: dev), (lambda seed=7: keep)
            try:
                fp0 = S._data_fingerprint()
                row = S.attempt(seed=3, tests=False)
            finally:
                S.dev_tasks, S.keep_tasks = old_dev, old_keep
            self.assertTrue(row["sandbox_clean"])
            self.assertEqual(row["organ"], "selfedit")
            log = [json.loads(l) for l in (Path(d) / "evolution.jsonl").read_text().splitlines()]
            self.assertEqual(log[-1]["seed"], 3)
            if not row["accepted"]:
                self.assertEqual(S._data_fingerprint(), fp0)
                self.assertFalse((Path(d) / "genome.json").exists())

    def test_should_respects_switch(self):
        with tempfile.TemporaryDirectory() as d, _Env(NOMAD_DATA=d, NOMAD_SELFEDIT="off"):
            self.assertFalse(S.should())
        with tempfile.TemporaryDirectory() as d, _Env(NOMAD_DATA=d, NOMAD_SELFEDIT="on"):
            self.assertTrue(S.should())
            (Path(d) / "evolution.jsonl").write_text(json.dumps({"organ": "selfedit", "gene": "inv_rounds",
                                                                  "ts": S._now()}) + "\n")
            self.assertFalse(S.should())   # an attempt in the last SELFEDIT_EVERY_MIN minutes


class Catalogue(unittest.TestCase):
    def test_reference_trees_match_truth(self):
        for f in ST.DEV_CATALOGUE + ST.CATALOGUE:
            rows = ST.draw_rows(f, random.Random(f"t:{f.family}"))
            self.assertEqual(len(rows), 11, f.family)
            for r, a in rows:
                self.assertEqual(run(f.tree, r), a, f.family)

    def test_input_names_disjoint(self):
        from nomad import science, transfer, transfer2, transfer3, transfer4
        other = set()
        for m in (science, transfer, transfer2, transfer3, transfer4):
            for f in m.CATALOGUE:
                other |= set(f.inputs)
        dev = {n for f in ST.DEV_CATALOGUE for n in f.inputs}
        sealed = {n for f in ST.CATALOGUE for n in f.inputs}
        self.assertFalse(dev & other)
        self.assertFalse(sealed & other)
        self.assertFalse(sealed & dev)
        self.assertFalse({f.family for f in ST.CATALOGUE} & {f.family for f in ST.DEV_CATALOGUE})


class SwitchExact(unittest.TestCase):
    def test_default_genome_on_equals_off(self):
        """The trained field on dev tasks: switch on with the default genome is byte-identical to off."""
        from nomad.world import evaluate
        p, vs = S.reference_field()
        for t in S.dev_tasks()[:4] + S.keep_tasks()[:4]:
            with _Env(NOMAD_SELFEDIT="off"):
                a = evaluate(t, prior=p, variation=vs, max_eval=3000, max_size=7, casesplit=True)[0]
            with _Env(NOMAD_SELFEDIT="on"), G.override(dict(G.DEFAULTS)):
                b = evaluate(t, prior=p, variation=vs, max_eval=3000, max_size=7, casesplit=True)[0]
            self.assertEqual((a.certified, a.evaluations, a.candidate), (b.certified, b.evaluations, b.candidate))


if __name__ == "__main__":
    unittest.main()
