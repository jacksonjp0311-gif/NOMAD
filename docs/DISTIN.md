# DISTIN: a budget-neutral LET2 guarded by refutation on in-domain inputs (pre-registered)

Switch `NOMAD_DISTIN` (default **off**). Option (1) of the Nov 27 plan, stronger functional certification
from a new angle. It is the fourth guard on LET2's early return (docs/LET2.md: sealed LET2 suite 9 -> 13,
FAIL on certification losses), after DISCRIM (veto by a disagreeing alternative on swapped inputs; vacuous
on `cl_h_rafts`; not budget-neutral), AGREE (positive support, budget-neutral; zero losses but kept none of
the gain) and CERT (evidence-mined properties, positive verification; nothing could be verified). It is
not MEMIDX, PRIMREC or CERT: it adds no memory, no primitive and no positive-verification rule.

No neural nets, no language model, no embeddings: enumeration, exact integer arithmetic, WITNESS.
Deterministic, CPU only.

## Design (`nomad/distin.py`, hook in `nomad/world.py`)

**Frame.** Exactly AGREE's (docs/AGREE.md, "The budget guarantee"): the let stage runs after main's PORT
stages have missed, paid only from MERGE's unspent probe-equivalence skips; every charge is checked
against the remaining skips before it is made; on a miss the stage's WITNESS rejections are forgotten and
the unspent skips are charged, so the task's program, receipt, certification and evaluations are
**identical to off**. An empty field never reaches the stage; the cold control never runs it.
NOMAD_LET2, NOMAD_DISCRIM, NOMAD_AGREE and NOMAD_CERT take precedence when on.

**Alternatives.** AGREE's set (the stage's other fits, offset quotients, value decompositions, the next
8 intermediates) plus DISCRIM's evidence-preserving simplifications, plus a new veto-only family,
**regroupings**: the floor division moved across a product (`A * (B // k)` <-> `(A * B) // k` <->
`(A // k) * B`), equal over the rationals and different exactly where the divisibility the evidence
happened to show fails. Each alternative is checked on the WITNESS evidence (1 evaluation each).

**New angle 1: where it asks.** The distinguishing inputs come from the task's own declared structure,
not from swaps: CERT's in-domain generator (each int input inside its observed range, a constant column
held at its constant, a pair ordering that holds on every evidence row kept; one input at a time moved to
the arithmetic edges of its base row: modulus block edges, range ends, neighbors, ties). A rival that
disagrees only on a swapped input (a count put where a size goes) asks a question the task never poses.

**New angle 2: what decides.** Refutation instead of positive support. The hit returns early unless:

- `rival`: an evidence-consistent alternative disagrees with it on an in-domain row and the largest class
  of mutually agreeing rivals is at least as large as the hit's own class (the hit and its independent
  supporters), or
- `relation`: it breaks a metamorphic relation that every evidence row satisfies, on an in-domain sweep:
  `mono` (output monotone in an input over the evidence; a sweep also includes the evidence rows on the
  same line) or `bound` (|out - x| within the evidence's largest deviation + 2). CERT's `mod` property is
  not used (docs/CERT.md: input-residue coincidences make it veto true functions).

A refuted hit is a miss (identical to off). A kept hit returns the smallest member of its agreement class
(AGREE's Occam rule; a different program is shown to WITNESS once more).

**No leakage.** Only `task.inputs` and the public + challenge rows are read; search gets `final=()`.
`tests/test_distin.py::test_decision_never_reads_final` checks poisoned final rows give the same decision.

**Controls (judge only).** `NOMAD_DISTIN_CONTROL=shuffled` (alternatives' and relation outcomes compared
on the wrong in-domain rows, rotated by one) and `rewired` (alternatives and relations evaluated on rows
whose int inputs are rotated and incremented by one). Memory control (report): the trained field with its
memory shuffled (`scripts/novel_judge.shuffled`, seed 1), DISTIN off and on.

## Dev (uncommitted dev suites in /workspace/nomad; tuned only there)

Fields: DISCRIM's dev fields (all_sci, practice). Suites as AGREE's dev: reason_dev (seeds 11/12), CEIL's
dev catalogue (seeds 31/37), guard suites (t5dev7, t6dev7, t7dev7, sdev7, sdev11); then sci_dev 7/11/13 and
the transfer dev list.

| dev set (all_sci / practice) | off | unguarded LET2 | AGREE | **DISTIN** | shuffled | rewired |
|---|---|---|---|---|---|---|
| reason + ceil + guard | 94 / 93 | 107 / 107 | 102 / 100 | **105 / 106** | 95 / 95 | 95 / 96 |
| sci + transfer dev list | 197 / 178 | 199 / 178 | 198 / 178 | **199 / 178** | 197 / 178 | 197 / 178 |

Losses (DISTIN vs off): 0 certification losses and 0 evaluation increases on tasks certified both ways, on
every dev set. Wrong early returns: unguarded LET2 2 on the first set (`cd_o_five`, `s5_all_handshakes`)
and 1 on the second (`k4_boxes_needed`); DISTIN 0 on the first and 1 on the second (`k4_boxes_needed`:
`t // cpb + 1` for a ceiling whose divisor is an input; the evidence never hit exact divisibility and no
alternative covers a variable-divisor ceiling; off does not certify it either, so it is not a loss).
Tuning steps, in order (bounded, two): (1) first version (AGREE alternatives + in-domain rows + relations):
105 / 106 with one wrong return (`s5_all_handshakes`, `(n - 1) * (n // 2)` on evidence where n was always
even, no rival); (2) added the regrouping rivals: same counts, that return refuted. A fix that mono sweeps
also include the evidence rows on the line (written for the `cl_h_rafts` unit case) changed no dev count.

`nv_d_round10` diagnostic (the decision function alone, rows drawn from the NOVEL formula at 300 dev seeds,
never the sealed rows): the lucky program `10 * ceil((nn - 1) / 10)` fit the 8 evidence rows at 21 seeds
and was refuted (`bound`) at all 21; the true program was refuted at 5 of 300 (evidence whose deviations
happened to stay <= 3). DISTIN does not gate PORT fits (that would not be budget-neutral); round10 is a
diagnostic of the decision, not part of the measured ability.

## Sealed suite (new, written before any field arm is measured)

`nomad/distin_tasks.py` (24 formulas: 8 plain two-stage, 4 ceilings, 3 roundings to the nearest k, 4
floor-division placements, 3 comparison / remainder traps, 2 one-step controls; domains orchard / foundry /
apiary, used by no other catalogue; new int inputs `fa fb fc fd`; family prefix `ds_`), generated once by
`scripts/distin_suite.py` (TRANSFER generator, seed **20271019**, unused: grep over docs/, results/,
scripts/, nomad/ and tests/ finds it nowhere else; used seeds include 20261120-20261231, 20270117,
20270203, 20270209, 20270223, 20270307, 20270331, 20270415, 20270419, 20270507, 20270521, 20270613,
20270803, 20270917): `data/deep/distin_suite.json`, sha256
`fbaf5cf756c012e822d617021c815a5ee746902f8f2dc879740b0a1b16b11c43`, 2 easy (`ds_ctl_one_step`,
`ds_ctl_one_step2`, never scored), **22 hard**, 0 lookup drops. Only the cold control and the lookup guard
were run.

Judge: `scripts/distin_judge.py` (budget 10,000; re-executes itself under `PYTHONHASHSEED=0`; arms cold /
empty_off / empty_on; for trained (all_sci, scored), math_sci and practice: off / **on** / let2 (unguarded,
report) / shuffled / rewired; shufmem_off / shufmem_on (report)). Measured **once**, from a snapshot of the
commit that adds this file.

## Pre-registered criteria (all must pass to flip the default, in a separate commit)

All runs pinned to `PYTHONHASHSEED=0`.

1. **It helps:** trained_on - trained_off >= 2 certified on the sealed DISTIN suite.
2. **Empty identical:** empty_on equals empty_off on every task (certified and evaluations); cold untouched.
3. **No loss on the sealed suite:** for trained, math_sci and practice, nothing certified off is lost on, no
   task certified both ways needs more evaluations on, nothing becomes newly worse than cold.
4. **The refutation carries it:** for each control (shuffled, rewired), summed over the three fields, `on`
   certifies strictly more than the control, or at least as many and the control loses (vs off) a task
   `on` keeps.
5. **Zero per-task losses on every existing judge:** `PYTHONHASHSEED=0 SWITCH=NOMAD_DISTIN
   scripts/switch_regress.py run OUT` over all 26 existing judges (the 25 listed in docs/AGREE.md plus agree),
   every arm judged: a loss is a task certified off but not on, or certified both with more evaluations on.
   Zero allowed.
6. **LET2's gain kept:** on the LET2 sealed suite (let2 judge, `trained_off` arm with DISTIN on) trained
   certifies >= 11 (off 9); the count against unguarded LET2's 13 is reported.
7. **Lucky fits rejected:** on the sealed DISTIN suite, `on` makes zero wrong early returns (a `port:let2`
   program that fails the final split) on every field.
8. **LOFO** (`distin_judge.py --lofo`): trained_distin total <= 5,883 and worst ratio <= 1.0x; the full
   test suite (`pytest tests`) passes.

Reported, not scored: unguarded LET2 and its wrong returns; the memory control (shufmem off / on); per-judge
certified totals and gains.

Decision rule: all eight -> `NOMAD_DISTIN` default ON in a separate commit; otherwise it stays OFF with an
honest write-up here and in `results/distin/`.
