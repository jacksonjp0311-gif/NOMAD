# DISCRIM: active distinguishing experiments (guarding LET2's fallback let fits)

Switch `NOMAD_DISCRIM` (default **off**). Motivation: LET2 (docs/LET2.md, 9b4296a) failed on 53 per-task
losses, including certification losses (transfer2 `g2_kite`, ceil `cl_h_rafts`, selfedit2 `se2_g_square9`,
meaning `ms_cake_split2`), because a let fit that reproduced every public and challenge row (so WITNESS
accepted it) was wrong on the final rows and returned before INVENT and the regular search ran. MERGE
tied. The external audit recommended **active distinguishing experiments**: when several distinct
programs fit all of the observed evidence, do not commit to the first one.

## Design

New module `nomad/discrim.py` (pure functions) and one guard inside the LET2 stage (`nomad/world.py`,
`discrim_guard`).

- **Where it acts.** With `NOMAD_DISCRIM=on`, LET2's fallback let stage runs (exactly as with
  `NOMAD_LET2=on`: after main's int anchor / anchor2 / scaled stages all missed, paid only from MERGE's
  unspent probe-equivalence skips, WITNESS rejections forgotten on a miss, the unspent skips charged
  afterwards so every later stage starts at main's count and main's gate). Every let fit WITNESS accepts
  then goes through a distinguishing experiment before it may return. `NOMAD_LET2=on` alone still runs
  the stage unguarded (the LET2 arm below). An empty field has no bank and never reaches the stage; the
  cold control is untouched.
- **Alternatives.** (a) the stage's other fits for the same intermediate `t` (already assembled), and
  (b) the hit's *evidence-preserving simplifications*: one sub-program replaced by a strictly smaller one
  (one of its own children, an input, or a constant 0-3) that has the same value on every evidence row.
  Each is a different explanation of the same observations (in the g2_kite failure mode,
  `max(A, Lz) * D / 2` vs `A * D / 2`, where `A > Lz` on every evidence row). At most `DISCRIM_ALT = 48`.
  An alternative survives when it reproduces every evidence row (WITNESS's own bar, `receipt.supported`).
- **Distinguishing inputs** (`discrim.rows`, `DISCRIM_N = 24`, deterministic: the generator state is a
  sha256 of the evidence inputs, so no hash-seed dependence), built from the task's input domain:
  1. *swaps*: an evidence row with the values of two same-typed inputs exchanged (tests an order between
     inputs that the evidence happens to satisfy);
  2. *recombinations*: each input's value taken from a different evidence row (keeps every input's
     observed values, breaks chance correlations);
  3. *spread*: int inputs drawn from the pooled range of all observed int values.
  A row equal to an evidence row is never used.
- **Decision** (`discrim.decide`): run the hit and every survivor on the distinguishing inputs. Two
  candidates *disagree* when some row gives both a valid, different value.
  - No survivor disagrees: **confirmed**, the hit returns (as in LET2).
  - Some survivor disagrees: **ambiguous**. The evidence cannot tell them apart, so the stage does not
    commit to the first fit. It returns the unique simplest explanation (MDL: the candidate with the
    fewest nodes, only when it is strictly smaller than every candidate that disagrees with it; it is
    shown to WITNESS like any fit), or, when there is none, nothing: the stage ends as a miss and main's
    later stages (block atoms, INVENT, the regular levels) run exactly as with the switch off.
- **Cost.** Each alternative checked on the evidence costs 1 evaluation; each candidate run on the
  distinguishing inputs costs 1. Everything is paid from the same LET2 budget (the unspent skips); out of
  budget counts as a miss. So the guard never makes a later stage start later than main.

### No leakage (how the final rows are kept out)

The discrimination step reads only `task.inputs` (names, types) and the rows of `task.public` and
`task.challenge`, which is exactly what WITNESS reads during search. `discrim.evidence(task)` returns
`public + challenge`; every other function in `nomad/discrim.py` receives those evidence rows (or the
inputs) as arguments and has no access to the task object's final split. `discrim_guard` calls only
`discrim.evidence`, `discrim.simplifications`, `discrim.fits` and `discrim.decide`; it never calls
`certify` (which computes `final_ok`). The distinguishing inputs carry **no expected outputs**: they are
only used to compare candidates with each other. `tests/test_discrim.py` checks that a task whose final
rows are poisoned gives an identical evidence set, identical distinguishing rows and an identical decision.

### Controls (judge-only)

- `NOMAD_DISCRIM_ROWS=evidence` (**blind**): the experiment reuses the evidence rows, so it can never
  disagree. This is the same stage with the experiment removed (equal to unguarded LET2 up to the
  guard's evaluation charge).
- `NOMAD_DISCRIM_ROWS=shuffled` (**shuffled**): each alternative's outcomes are compared on the wrong
  distinguishing rows (rotated by one), so disagreements no longer mean anything.
- `NOMAD_DISCRIM_PICK=fall`: on ambiguity never pick, always keep searching (dev only).

## Dev (uncommitted dev suites in /workspace/nomad, tuned only there)

Parameters (`DISCRIM_N`, `DISCRIM_ALT`, the three row kinds, and MDL pick vs. fall-through) were chosen on
the dev suites below. One existing-suite case, `g2_kite` (whose failure mode docs/LET2.md already
describes), was re-run once to confirm the failure mode before the design was written; no parameter was
tuned on any committed suite.

| dev set (fields math_sci / practice unless noted) | off | DISCRIM, pick=fall | DISCRIM, pick=mdl (chosen) | losses |
|---|---|---|---|---|
| reason_dev two-stage (24 tasks, seeds 11/12): all_sci / practice | 12 / 13 | 14 / 16 | **15 / 17** | 0 |
| same, controls: unguarded LET2 / blind / shuffled (all_sci / practice) | | | 15/17, 15/17, 14/17 | 0 |
| guard suites (t5dev7, t6dev7, t7dev7, sdev7, sdev11) | 78 / 74 | 83 / 78 | **85 / 80** | 0 |
| sci_dev 7/11/13 + transfer dev list (t2dev7/11, dev7/11/13, t4dev7, t3dev7) | 197 / 178 | - | **199 / 178** | 0 |

Losses: 0 certification losses and 0 evaluation increases on tasks certified both ways, on every dev
set. Fall-through lost two correct LET2 fits (e.g. reason `d_change_coins`: the let fit
`cd // a - min(cd, b)` is ambiguous with the simpler `cd // a - b`, which is the truth); MDL keeps them.
On the dev sets the controls are close to `on`: the dev suites contain few ambiguous fits, which is why
the sealed suite below is built around them.

## Sealed suite (new, written before any field arm is measured)

`nomad/discrim_tasks.py` (22 two-stage formulas + 2 one-step controls; domains lighthouse / glacier /
pottery, used by no other catalogue; new int inputs `dj dk dl dm`; family prefix `dx_`). Ambiguity by
construction: the input ranges overlap only partly (`dj` 1-30, `dk` `dl` 1-12, `dm` 1-9), so an order
between two inputs often holds on the 8 evidence rows by chance; half of the formulas are plain two-stage
computations, half contain a comparison, a capped difference or a remainder whose branch the evidence may
never exercise. Generated once by `scripts/discrim_suite.py` (TRANSFER generator, seed **20270419**,
unused by any earlier suite): `data/deep/discrim_suite.json`, sha256
`55042ce2bf27707db025c1b0a5b9d66ca0bcbc27b2ba89ee136e31d2d9537d94`, 2 easy (cold certifies:
`dx_floe_area_half`, `dx_ctl_one_step`; never scored), **22 hard** (incl. the control `dx_ctl_one_step2`,
which the cold control did not certify), 0 lookup drops. Only the cold control was run.

Judge: `scripts/discrim_judge.py` (budget 10,000; arms cold / empty_off / empty_on; for trained (all_sci,
scored), math_sci and practice: off / **on** / let2 (unguarded, report) / blind control / shuffled
control). Measured once, from a snapshot of the commit that adds this file.

## Pre-registered criteria (all must pass to flip the default, in a separate commit)

1. **It helps:** trained_on - trained_off >= 2 certified on the sealed DISCRIM suite.
2. **Empty identical:** empty_on equals empty_off on every task (certified and evaluations); cold untouched.
3. **No loss on the sealed suite:** for trained, math_sci and practice, nothing certified off is lost on,
   no task certified both ways needs more evaluations on, and nothing becomes newly worse than cold
   (empty_on included).
4. **The experiment carries it:** for each control (blind, shuffled), summed over the three fields, `on`
   certifies strictly more than the control, or certifies at least as many and the control loses
   (vs off) at least one task that `on` keeps.
5. **No loss anywhere else:** `SWITCH=NOMAD_DISCRIM scripts/switch_regress.py` over learning, transfer1-4,
   secondary4, text, bridge, text_invent, route5, transfer6, selfedit2, text_chain, meaning, inflect, let,
   textpat, roles, combine, ceil, merge, let2 (22 judges): **zero per-task losses** by switch_regress's own
   definition (certified off but not on, or more evaluations on when certified both ways). For the let2
   judge, the arms that run with `NOMAD_LET2=on` (`*_on`, `*_pool`: the unguarded stage this switch
   guards) are reported, not judged; its `cold`, `empty_off` and `*_off` arms are judged.
6. **LOFO** (`discrim_judge.py --lofo`): trained_discrim total <= 5,883 and worst ratio <= 1.0x; the full
   test suite passes.
7. Report only: on vs unguarded LET2 per field; on the LET2 sealed suite and the 21 judges where LET2
   lost, whether DISCRIM keeps LET2's gain (let2 judge, `*_off` arms with DISCRIM on, vs LET2's 9 -> 13)
   without its losses.
