"""NOVEL (docs/NOVEL.md): the never-trained generalization measurement. Measurement only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import novel_catalogue as NC  # noqa: E402
import novel_judge as NJ  # noqa: E402
import novel_suite as NS  # noqa: E402
from nomad.world import run, size  # noqa: E402
from nomad.world_tasks import all_training  # noqa: E402


def test_suite_hash_and_shape():
    suite, easy, hard = NS.load(NS.OUT, check=True)
    assert suite["seed"] == NS.SEED == 20270613
    assert len(hard) == 26 and len(easy) == 2
    for t in hard + easy:
        assert (len(t.public), len(t.challenge), len(t.final)) == (5, 3, 3)


def test_rows_are_exact_reference_answers():
    suite = json.loads(NS.OUT.read_text())
    for e in suite["hard"] + suite["easy"]:
        f = NC.BY_FAMILY[e["family"]]
        for row, ans in e["rows"]:
            assert NC.exact_answer(f, row) == ans == run(f.tree, row)


def test_inputs_never_trained():
    trained = {n for t in all_training() for n, _ in t.inputs}
    novel = {n for f in NC.CATALOGUE for n in f.inputs}
    assert not trained & novel


def test_old_switches_differ_only_in_post_nov20():
    diff = {k for k in NJ.CURRENT if NJ.CURRENT[k] != NJ.OLD[k]}
    assert diff == set(NJ.POST_NOV20)
    assert all(NJ.OLD[k] == "off" for k in NJ.POST_NOV20)


def test_rewire_keeps_shape():
    import random
    t = ["add", ["max", ["var", "a"], ["var", "b"]], ["mul", ["const", 2], ["var", "c"]]]
    r = NJ.rewire_tree(t, random.Random(1))
    assert size(r) == size(t) and r[1][1] == ["var", "a"] and r[2][1] == ["const", 2]
    assert t == ["add", ["max", ["var", "a"], ["var", "b"]], ["mul", ["const", 2], ["var", "c"]]]
