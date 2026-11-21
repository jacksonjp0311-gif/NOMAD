# LET2: safe multi-step reasoning (let-bindings as a fallback, paid only from saved evaluations)

Switch `NOMAD_LET2` (default **off**). Second attempt at NOMAD_LET (docs/LET.md: trained 12 vs 8, but FAIL
on 119 per-task losses on earlier suites, including `sci_water_mol`, because LET's stage spent the task's
own budget and WITNESS rejections ahead of later stages).

## Design (one change of placement and funding; LET's stage itself is reused unchanged)

- With the switch on, the PORT bank is MERGE's `MergedBank` (docs/MERGE.md machinery: main's bank element
  for element, probe-equivalent duplicates copy their values instead of being re-evaluated, an anchor
  lookup that already missed is not repeated). Main's stages see the *virtual* count (real + unspent skips),
  so they produce exactly main's candidates in main's order. NOMAD_MERGE's own merged-anchor stage stays off
  unless NOMAD_MERGE is on.
- After main's int anchor / anchor2 / scaled / LET(off) stages have **all missed**, LET's let stage
  (`let_stage`: bind a certified bank block `t`, form one-step terms over t, assemble
  `f(t) op g(t)` / residual / scale fits, WITNESS-gated, <= LET_REJECTS = 2 rejections) runs with a budget
  of **only the unspent skips** (real evaluations, never past main's limit).
- On a miss, the WITNESS rejections it caused are removed from the gate (`LET2_RESTORE`), and the unspent
  skips are charged (`merge_settle`), so every later stage starts at main's evaluation count and main's
  gate state. A task main certifies before this point is untouched; a task main certifies after it sees
  the same count and gate. An empty field has no bank and never reaches it; the cold control is untouched.
- If NOMAD_MERGE is also on, LET2 runs before MERGE's merged anchors (both share the same skips).
- Caveat: the budget is only the skips (typically a few hundred evaluations per task), and a hit found
  by LET2 consumes up to 2 WITNESS consults that main would not have spent (the hit itself is the
  same certification bar).

## Dev (uncommitted dev suites in /workspace/nomad, tuned only there)

| dev set | off | on | losses |
|---|---|---|---|
| reason_dev two-stage (24 tasks, seeds 11/12): all_sci / practice / math_sci | 12 / 13 / 12 | 15 / 17 / 15 | 0 |
| same, with NOMAD_MERGE also on, before LET2_RESTORE | - | 13 / 13 / - | 1 (practice d_t_max: an extra-stage rejection changed later gate behaviour) |
| same, with NOMAD_MERGE also on, LET2_RESTORE + LET2 first | - | 15 / 17 / 15 | 0 |
| merge_dev dev (practice / math_sci) | 149 / 159 | 149 / 161 | 0 |
| science dev (sci_water_mol kept; all_sci / math_sci) | 38 / 38 | 38 / 38 | 0 |
| guard suites (t5dev7, t6dev7, sdev7, sdev11; math_sci / practice / all_sci) | 62 / 57 / 62 | 68 / 64 / 68 | 0 |
| pool control (NOMAD_LET_SOURCE=pool) on reason_dev | - | 14 / 17 / 14 | - |
| pool control on guard suites (math_sci / practice) | - | 68 / 64 | - |

Expectation stated before the sealed measurement: as with LET, the pool control (binding the probe's own
unlearned values instead of the field's blocks) will be close to `on`. The gain is therefore expected to
come from the let operator reached safely, not from the field's learned blocks as intermediates; the
control is **reported, not a pass criterion**.

## Sealed suite (new, written before any field arm is measured)

`nomad/let2_tasks.py` (22 two-stage formulas + 2 one-step controls; domains garden / workshop / market;
new int inputs `hu hv hw hx`; new family names `k2_*`), generated once by `scripts/let2_suite.py` (TRANSFER
generator, seed **20270331**, unused): `data/deep/let2_suite.json`, sha256
`d045282fe9d715d816153cf553baa94bda9fb4d084b33294a16a97a974fdfec7`, 2 easy (controls, never scored),
22 hard, 0 lookup drops. Only the cold control was run.

Judge: `scripts/let2_judge.py` (budget 10,000; arms cold / empty_off / empty_on; for trained (all_sci,
scored), math_sci and practice: off / on / pool control). Measured once, from a snapshot of the commit
that adds this file.

## Pre-registered criteria (all must pass to flip the default, in a separate commit)

1. **It helps:** trained_on - trained_off >= 2 certified on the sealed LET2 suite.
2. **Empty identical:** empty_on equals empty_off on every task (certified and evaluations).
3. **No loss on the sealed suite:** for trained, math_sci and practice, nothing certified off is lost on,
   and nothing becomes newly worse than cold (empty_on included).
4. **No loss anywhere else:** `SWITCH=NOMAD_LET2 scripts/switch_regress.py` over learning, transfer1-4,
   secondary4, text, bridge, text_invent, route5, transfer6, selfedit2, text_chain, meaning, inflect, let,
   textpat, roles, merge: zero certification losses switch on vs off (evaluation changes reported, not
   judged). COMBINE and CEIL are excluded (their owners have not measured them yet).
5. **LOFO** (`let2_judge.py --lofo`): trained_let2 total <= 5,883 and worst ratio <= 1.0x; full pytest passes.
6. Report only: pool control per field; on vs empty_on vs cold.

### Addendum to criterion 4 (owner instruction; written after the sealed LET2 suite run started, before any regression run)

COMBINE and CEIL have now been measured by their owners (results/combine, results/ceil), so their judges
are **added** to criterion 4: learning, transfer1-4, secondary4, text, bridge, text_invent, route5,
transfer6, selfedit2, text_chain, meaning, inflect, let, textpat, roles, combine, ceil, merge. This only
makes the criterion stricter. Per-task evaluation increases on certified tasks are also listed (as CEIL
did) and are reported next to the certification verdict. Measured from the snapshot of `0f97201`.

## Sealed result, part 1: LET2 suite (measured once from the 0f97201 snapshot; regressions and LOFO pending)

sha d045282f, 22 hard (`results/let2/let2_sealed.json`):

| arm | off | on | pool control |
|---|---|---|---|
| cold | 0 | | |
| empty | 0 | 0 (identical per task) | |
| trained (all_sci) | 9 (181,421 evals) | **13** (169,282) | 12 |
| math_sci | 9 | 13 | 12 |
| practice | 8 (186,747) | 10 (180,665) | 11 |

- Criterion 1 pass (+4, bar +2).
- Criterion 2 pass.
- Criterion 3 pass: 0 lost on any field; nothing newly worse than cold.
- Report: as expected before measuring, the pool control is close (12 / 12 / 11). The gain comes from the
  let operator reached safely, not from the field's blocks as intermediates.
