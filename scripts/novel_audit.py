"""Post-hoc audit (report only): is each certified program right beyond the 11 sealed rows?"""
import json, random, sys
from fractions import Fraction as F
sys.path.insert(0, '.'); sys.path.insert(0, 'scripts')
import novel_catalogue as NC
from nomad.world import run, Invalid
from nomad.science import _draw

def parse(s):
    import re
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|-?\d+|[(),]", s)
    pos = 0
    def expr():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t.lstrip('-').isdigit(): return ["const", int(t)]
        if pos < len(toks) and toks[pos] == "(":
            pos += 1; args = []
            while toks[pos] != ")":
                args.append(expr())
                if toks[pos] == ",": pos += 1
            pos += 1
            return [t] + args
        return ["var", t]
    return expr()

o = json.load(open('results/novel/novel_judge.json'))
per = o['per_task[certified, evals, via, candidate]']
out = {}
for fam, arms in per.items():
    f = NC.BY_FAMILY[fam]
    rows = []
    rng = random.Random(f"audit:{fam}")
    tries = 0
    while len(rows) < 2000 and tries < 200000:
        tries += 1
        r = {k: _draw(rng, f.ranges[k]) for k in f.inputs}
        a = NC.exact_answer(f, r)
        if a is not None: rows.append((r, a))
    for arm, (c, ev, via, cand) in arms.items():
        if not c: continue
        t = parse(cand)
        bad = 0
        for r, a in rows:
            try: g = run(t, r)
            except Invalid: g = None
            bad += g != a
        out.setdefault(fam, {})[arm] = {"program": cand, "rows_checked": len(rows), "wrong": bad}
print(json.dumps(out, indent=1))
