"""Measurement only (docs/LIVE_WORDS.md): N body world cycles on a temp copy of data/, NOMAD_LIVE_WORDS off|on.

    python3 scripts/live_words_smoke.py on 450
"""
import json, os, shutil, sys, tempfile, time
W=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, W)
mode, n = sys.argv[1], int(sys.argv[2])
d = tempfile.mkdtemp(prefix=f"nomad-lw-{mode}-")
shutil.copytree(W + '/data', d, dirs_exist_ok=True)
os.environ['NOMAD_DATA'] = d; os.environ['NOMAD_LIVE_WORDS'] = mode; os.environ['NOMAD_LIVE_BRIDGE'] = 'on'
from nomad.world_loop import world_pair, load_world_prior
from nomad.consolidate import consolidate
rows = []; t0 = time.time()
for i in range(n):
    a = time.time(); o = world_pair(); dt = time.time() - a
    rows.append({"family": o["family"], "domain": o["domain"], "c": o["control"]["certified"], "t": o["treatment"]["certified"],
                 "ce": o["control"]["evaluations"], "te": o["treatment"]["evaluations"], "via": o["treatment"]["via"], "s": round(dt, 2)})
    if i % 3 == 2:
        consolidate()
p = load_world_prior()
from nomad.world_loop import probe_heldout
ph = probe_heldout(write=False)
late=[r for r in rows[n//2:] if r["domain"]!="words"]
nonw = [r for r in rows if r["domain"] != "words"]; w = [r for r in rows if r["domain"] == "words"]
print(json.dumps({"mode": mode, "cycles": n, "seconds": round(time.time() - t0, 1),
  "non_word": {"n": len(nonw), "treat_cert": sum(r["t"] for r in nonw), "ctrl_cert": sum(r["c"] for r in nonw),
               "treat_evals": sum(r["te"] for r in nonw), "sec_per_cycle": round(sum(r["s"] for r in nonw)/max(1,len(nonw)), 2)},
  "word": {"n": len(w), "treat_cert": sum(r["t"] for r in w), "ctrl_cert": sum(r["c"] for r in w),
           "via_meaning": sum(bool(r["via"] and r["via"].startswith("meaning:")) for r in w),
           "treat_evals": sum(r["te"] for r in w), "ctrl_evals": sum(r["ce"] for r in w),
           "sec_per_cycle": round(sum(r["s"] for r in w)/max(1,len(w)), 2)},
  "heldout": {k: v["kind"] for k, v in ph["probes"].items()}, "late_non_word": {"n": len(late), "treat_cert": sum(r["t"] for r in late), "ctrl_cert": sum(r["c"] for r in late), "treat_evals": sum(r["te"] for r in late), "ctrl_evals": sum(r["ce"] for r in late)}, "lexicon_tokens": len(p.lexicon), "concepts": len(p.concepts), "rows": rows}, indent=1))
