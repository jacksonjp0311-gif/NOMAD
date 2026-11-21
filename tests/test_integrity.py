"""INTEGRITY (docs/INTEGRITY.md): evidence-loop defects reported by an external audit.

Each test first reproduced a defect on the pre-fix code (it failed there), then pins the fix:

1. receipt binding: a WITNESS receipt admits only the exact program (hash) and task it attests;
2. crash replay: a packet applied before a crash is not applied again on the next sleep;
3. challenge/final separation: WITNESS consultation during search cannot reach the final split,
   and search receives a task view with no final rows.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _inc_task():
    from nomad.world import make_task
    rows = lambda xs: [({"x": x}, x + 1) for x in xs]
    return make_task("t-inc", "integrity_inc", "int", {"x": "int"}, "int",
                     rows([1, 2, 3, 5, 8]), rows([13, 21, 34]), rows([55, 89, 144]))


ADD1 = ["add", ["var", "x"], ["const", 1]]
MUL2 = ["mul", ["var", "x"], ["const", 2]]


class ReceiptBinding(unittest.TestCase):
    def test_receipt_for_add1_does_not_admit_mul2(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, fin = certify(t, ADD1)
        self.assertTrue(receipt.supported and receipt.verify_checksum() and fin)
        p = WorldPrior()
        with self.assertRaises(ValueError):
            p.add_witnessed(MUL2, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs)
        self.assertEqual(p.witnessed, 0)
        self.assertEqual(p.programs, {})
        self.assertEqual(p.families, {})

    def test_matching_tree_still_admitted(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, _fin = certify(t, ADD1)
        p = WorldPrior()
        p.add_witnessed(ADD1, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs,
                        task_id=t.task_id)
        self.assertEqual(p.witnessed, 1)

    def test_task_identity_bound(self) -> None:
        from nomad.world import OPSETS, WorldPrior, certify
        t = _inc_task()
        receipt, _pub, _fin = certify(t, ADD1)
        p = WorldPrior()
        with self.assertRaises(ValueError):
            p.add_witnessed(ADD1, receipt, family=t.family, opset=OPSETS["int"], inputs=t.inputs,
                            task_id="some-other-task")
        self.assertEqual(p.witnessed, 0)

    def test_genesis_prior_binds_candidate(self) -> None:
        from nomad.genesis import GrammarPrior, evaluate_task
        from nomad.simulation_v10 import make_tasks
        t = make_tasks(131, ("square_plus",), n_per_family=1)[0]
        ev, receipt = evaluate_task(t)
        self.assertTrue(receipt is not None and receipt.supported)
        other = "(x+y)" if ev.candidate != "(x+y)" else "(x*y)"
        prior = GrammarPrior()
        with self.assertRaises(ValueError):
            prior.add_witnessed(ev.learned_context, other, receipt)
        self.assertEqual(prior.witnessed, 0)
        prior.add_witnessed(ev.learned_context, ev.candidate, receipt)
        self.assertEqual(prior.witnessed, 1)
