#!/usr/bin/env python3
"""Standalone consumer check for NOMAD feed packets (stdlib only, Python 3.8+).

Copy this one file into any consumer (agent-colony, locus, ...). It needs
nothing from NOMAD's package. It reimplements the tiny typed DSL (nomad.world DSL v1) and checks:

  1. packet_sha256 = sha256(canonical JSON of the packet without packet_sha256)
     and, with --manifest, that prev_sha256 / packet_sha256 sit in NOMAD's chain;
  2. every evidence program reproduces every public, challenge and final row;
  3. every block's tree_sha256 matches and the block is a subtree of a program
     listed in its certified_in that passed check 2.

It does NOT re-attest WITNESS receipts (that needs NOMAD's deterministic
witness); run `python -m nomad.feed verify` inside NOMAD for that. Passing
this check says the packet is intact and its programs do what it claims on the
shipped rows. It says nothing about value on your tasks: measure blocks against
your own cold control.

Usage:  python3 nomad_feed_check.py latest.json [--manifest manifest.json]
Exit 0 = ok, 1 = failures (printed as JSON), 2 = bad usage / unreadable file.
"""
import hashlib
import json
import sys

MAX_INT = 10 ** 6
MAX_STR = 64
MAX_LIST = 32


class Invalid(Exception):
    pass


def _int(v):
    if isinstance(v, bool) or not isinstance(v, int) or abs(v) > MAX_INT:
        raise Invalid
    return v


def _str(v):
    if len(v) > MAX_STR:
        raise Invalid
    return v


def _ne(xs):
    if not xs:
        raise Invalid
    return xs


def _div(a, b):
    if b == 0:
        raise Invalid
    return _int(a // b)  # floor division (Python semantics: -7 // 2 == -4)


def _mod(a, b):
    if b == 0:
        raise Invalid
    return _int(a % b)  # result takes the divisor's sign (Python semantics)


# name: (argument types, output type, function). Lists are int lists (tuples here).
OPS = {
    "add": (("int", "int"), "int", lambda a, b: _int(a + b)),
    "sub": (("int", "int"), "int", lambda a, b: _int(a - b)),
    "mul": (("int", "int"), "int", lambda a, b: _int(a * b)),
    "div": (("int", "int"), "int", _div),
    "mod": (("int", "int"), "int", _mod),
    "min": (("int", "int"), "int", lambda a, b: min(a, b)),
    "max": (("int", "int"), "int", lambda a, b: max(a, b)),
    "ite": (("int", "int", "int"), "int", lambda c, a, b: a if c > 0 else b),
    "upper": (("str",), "str", lambda s: s.upper()),
    "lower": (("str",), "str", lambda s: s.lower()),
    "srev": (("str",), "str", lambda s: s[::-1]),
    "concat": (("str", "str"), "str", lambda a, b: _str(a + b)),
    "first": (("str",), "str", lambda s: s[:1]),
    "last": (("str",), "str", lambda s: s[-1:]),
    "strlen": (("str",), "int", lambda s: len(s)),
    "sort": (("list",), "list", lambda xs: tuple(sorted(xs))),
    "lrev": (("list",), "list", lambda xs: xs[::-1]),
    "tail": (("list",), "list", lambda xs: xs[1:]),
    "sum": (("list",), "int", lambda xs: _int(sum(xs))),
    "len": (("list",), "int", lambda xs: len(xs)),
    "lmax": (("list",), "int", lambda xs: max(_ne(xs))),
    "lmin": (("list",), "int", lambda xs: min(_ne(xs))),
    "head": (("list",), "int", lambda xs: _ne(xs)[0]),
}


def type_of(v):
    if isinstance(v, bool):
        return "bad"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return "str"
    if isinstance(v, tuple):
        return "list"
    return "bad"


def freeze(v):
    """JSON value -> DSL value (JSON lists become int tuples, bounded)."""
    if isinstance(v, list):
        t = tuple(v)
        if len(t) > MAX_LIST or any(type_of(x) != "int" or abs(x) > MAX_INT for x in t):
            raise Invalid
        return t
    return v


def run(tree, row, depth=0):
    """Evaluate a tree: ["var", name] | ["const", k] | [op, child, ...]."""
    if depth > 64 or not isinstance(tree, list) or not tree:
        raise Invalid
    tag = tree[0]
    if tag == "var":
        if tree[1] not in row:
            raise Invalid
        return row[tree[1]]
    if tag == "const":
        return int(tree[1])
    spec = OPS.get(tag)
    if spec is None or len(tree) - 1 != len(spec[0]):
        raise Invalid  # includes "lib": shipped programs must be standalone
    args = [run(c, row, depth + 1) for c in tree[1:]]
    for a, t in zip(args, spec[0]):
        if type_of(a) != t:
            raise Invalid
    try:
        return spec[2](*args)
    except (ValueError, TypeError, IndexError, OverflowError):
        raise Invalid


def subtrees(tree):
    yield tree
    if tree[0] not in ("var", "const", "lib"):
        for c in tree[1:]:
            yield from subtrees(c)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def packet_hash(packet):
    return hashlib.sha256(canonical({k: v for k, v in packet.items() if k != "packet_sha256"})).hexdigest()


def rows_ok(program, rows):
    for inputs, expected in rows:
        try:
            got = run(program, {k: freeze(v) for k, v in inputs.items()})
        except Invalid:
            return False
        if got != freeze(expected):
            return False
    return True


def check(packet, manifest=None):
    failures, checks = [], 0
    checks += 1
    if packet.get("schema") != "nomad.feed.packet.v1":
        failures.append("schema")
    checks += 1
    if packet_hash(packet) != packet.get("packet_sha256"):
        failures.append("packet_sha256")
    if manifest is not None:
        checks += 1
        chain = [p.get("sha256") for p in manifest.get("packets", [])]
        h, prev = packet.get("packet_sha256"), packet.get("prev_sha256")
        if h not in chain:
            failures.append("manifest:not_in_chain")
        elif prev is not None and (chain.index(h) == 0 or chain[chain.index(h) - 1] != prev):
            failures.append("manifest:prev_mismatch")
    progs = {}
    for e in packet.get("evidence", []):
        checks += 1
        task = e.get("task", {})
        tid = task.get("task_id")
        rows = task.get("public", []) + task.get("challenge", []) + task.get("final", [])
        if not rows or not rows_ok(e.get("program"), rows):
            failures.append("evidence:%s:rows" % tid)
            continue
        progs[tid] = e["program"]
    for b in packet.get("blocks", []):
        checks += 1
        if hashlib.sha256(canonical(b.get("tree"))).hexdigest() != b.get("tree_sha256"):
            failures.append("block:%s:tree_sha256" % b.get("block_id"))
            continue
        if not any(t in progs and b["tree"] in list(subtrees(progs[t])) for t in b.get("certified_in", [])):
            failures.append("block:%s:no_certified_use" % b.get("block_id"))
    return {"ok": not failures, "checks": checks, "failures": failures,
            "witness_reattested": False}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    try:
        packet = json.load(open(argv[0], encoding="utf-8"))
        manifest = None
        if "--manifest" in argv:
            manifest = json.load(open(argv[argv.index("--manifest") + 1], encoding="utf-8"))
    except (OSError, ValueError, IndexError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    out = check(packet, manifest)
    print(json.dumps(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
