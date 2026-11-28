"""Body-side composition finder.

After a held-out probe returns none, try short programs from the probe opset.
If one certifies and cold does not, record it as an unapplied suggestion.
The next sleep's apply_pending absorbs it. The body remains the authority.
"""
from __future__ import annotations

import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import data_root
from .world import Invalid, OPSETS, consult
from .world import run as world_run
from .world_tasks import HELDOUT


def _tree_certifies(task: Any, tree: list) -> bool:
    try:
        vals = [world_run(tree, r) for r, _e in task.public]
    except (Invalid, Exception):
        return False
    if vals != [e for _r, e in task.public]:
        return False
    receipt = consult(task, tree)
    return receipt is not None and receipt.supported


def _find(task: Any, name: str, max_try: int = 512) -> list | None:
    if not task.inputs:
        return None
    kind = task.inputs[0][1]
    var = task.inputs[0][0]
    ops = list(OPSETS.get(kind, ()))
    tokens = set(re.findall(r"[a-z]+", name.lower()))
    preferred = [o for o in ops if o in tokens or any(t in o for t in tokens)]
    base = ["var", var]
    # binary of unaries
    for op, a, b in itertools.product(ops, ops, ops):
        tree = [op, [a, base], [b, base]]
        if _tree_certifies(task, tree):
            return tree
    # name-token nested
    binaries = [o for o in ops if o in ("concat", "sub", "add", "mul")]
    # include common string/list atoms so nested forms are reachable
    atoms = [o for o in ops if o in ("upper", "lower", "first", "last", "srev", "sum", "lmax", "lmin", "head", "tail")]
    prefs = preferred or atoms or ops[:6]
    count = 0
    for bop in binaries:
        for a, c in itertools.product(prefs, repeat=2):
            for x, y in itertools.product(prefs, repeat=2):
                if count >= max_try:
                    return None
                tree = [bop, [a, [x, base]], [c, [y, base]]]
                count += 1
                if _tree_certifies(task, tree):
                    return tree
    return None


def suggest_for_none(probes: dict[str, Any]) -> list[dict]:
    """For probes that returned none, find a short program and record it."""
    out = []
    path = data_root() / "interlink_feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name, row in probes.items():
        if row.get("kind") != "none":
            continue
        if name not in HELDOUT:
            continue
        task = HELDOUT[name]["task"]
        tree = _find(task, name)
        if tree is None:
            continue
        s = {
            "ts": now,
            "probe": name,
            "tree": tree,
            "note": "Body composition found. Body remains authority.",
            "applied": False,
        }
        with path.open("a") as f:
            f.write(json.dumps(s) + "\n")
        out.append(s)
    return out
