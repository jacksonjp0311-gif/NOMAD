# AGREE: a budget-neutral LET2 with an agreement guard (pre-registered)

Switch `NOMAD_AGREE` (default **off**). Third attempt at LET2's gain (docs/LET2.md: sealed LET2 suite 9 -> 13,
FAIL on 53 per-task losses on 6 judges, including certification losses `g2_kite`, `cl_h_rafts`,
`se2_g_square9`, `ms_cake_split2`) after DISCRIM (docs/DISCRIM.md: kept the 9 -> 13, removed every LET2
certification loss except `cl_h_rafts`, FAIL on 48 losses). DISCRIM's diagnosis: `cl_h_rafts`' wrong let fit
`t // 2 - t // 3` (for `ceil(t / 6)`) had **no surviving alternative at all**, so the distinguishing
experiment was empty and "confirmed" it vacuously. Its note 1 proposed **positive support**: return only when
an independently derived alternative agrees. AGREE is that rule, made budget-neutral in the CLAUSE2 sense
(f5b8631): a miss is identical to off.

No neural nets, no language model, no embeddings: enumeration, exact integer arithmetic, WITNESS.
Deterministic (no hash-seed dependence in the guard; every judge run pinned to `PYTHONHASHSEED=0`), CPU only.

## Design

Where it acts: exactly LET2's place. With `NOMAD_AGREE=on` (and `NOMAD_LET2`, `NOMAD_DISCRIM` off; when either
of those is on it takes precedence and AGREE does nothing), the PORT bank is MERGE's `MergedBank`; after
main's int anchor / anchor2 / scaled stages have all missed, LET's let stage runs with a budget of **only the
unspent probe-equivalence skips** (real evaluations, never past main's limit). Every let fit WITNESS accepts
then goes through the agreement guard (`world.agree_guard`, `nomad/agree.py`):

1. **Independent alternatives** (assembled from something other than the hit's own decomposition):
   - the stage's other fits for the same intermediate `t` (a different pair of one-step terms);
   - further decompositions over values already computed (`agree_fits`, no evaluation, like LET's residual
     lookups): a scaled residual `a op (b * k)` (k = 2, 3) and `max(a, b)` / `min(a, b)` of two terms;
   - offset quotients `(t + c) // k`, `(t - c) // k` (c = 0..3; k = 2, 3, then the field's learned scales;
     at most `AGREE_DIVS = 6` divisors), each 1 evaluation; a fit when the goal is the quotient or the
     quotient plus / minus a constant 1-3;
   - LET's fits (and the decompositions above) over the next `AGREE_T = 8` bound intermediates of the same
     bounded let search (each new term 1 evaluation, as in the stage).
   At most `AGREE_ALT = 48`, deduplicated up to commutative operand order. Each is checked on the WITNESS
   evidence (public + challenge rows, `receipt.supported`'s bar): 1 evaluation each.
2. **Rivals** are any alternative (independent, or one of the hit's evidence-preserving simplifications from
   DISCRIM, which are veto-only) that fits the evidence but **disagrees** with the hit on DISCRIM's
   deterministic distinguishing inputs (swaps / recombinations / spread of the evidence inputs; no expected
   outputs; 1 evaluation per compared program).
3. **Decision** (`agree.decide`): *supported* when at least one independent alternative agrees with the hit
   (same value on every distinguishing row where both are valid, on at least `AGREE_MIN_ROWS = 8` rows) and
   the hit's class (the hit plus its supporters) is **strictly larger** than the largest class of mutually
   agreeing rivals. Then the smallest member of the agreement class is returned (the hit unless a supporter
   or agreeing simplification is strictly smaller; a different program is shown to WITNESS once more,
   1 evaluation). Otherwise (*unsupported* or *vetoed*) the stage ends as a **miss**.

### The budget guarantee (stated precisely)

For every task, with `NOMAD_AGREE` on versus off (all else equal):

1. Main's stages before the let stage produce exactly main's candidates in main's order at main's
   (virtual) count (MERGE's MergedBank: probe-equivalent blocks copy values; their evaluations are
   *skips*, docs/MERGE.md).
2. The let stage and the guard spend only real evaluations from the unspent skips: every charge is checked
   against `limit = evals + skips - spent` *before* it is made (the candidate fit and its possible WITNESS
   rejection must both fit: `evals + 2 <= limit`). Out of budget = miss.
3. On a **miss**, the WITNESS rejections the stage caused are removed from the gate (`LET2_RESTORE`) and the
   unspent skips are charged (`merge_settle`), so every later stage starts at main's count with main's gate
   and runs main's search unchanged: the task's program, receipt, certification and reported evaluations are
   **identical to off**. (Tests: `test_a_miss_is_identical_to_off`, where the guard runs and finds no
   support; `test_forced_misses_are_identical_to_off`, every guard decision forced to a miss.)
4. On a **hit**, the program returns at a count `<= ` main's count at that point (so `<=` off's count for
   the same task when off certifies later); it is certified by WITNESS and the independent final split
   like any other.
5. An empty field has no bank and never reaches the stage; the cold control never runs it.

What it does **not** guarantee: a hit is a different program than off's later find, so it can still pass
WITNESS and fail the final split where off's later program passes (a certification loss), and a hit on a
**training** task changes what the field learns (later tasks can then take a different path). Criterion 5
counts both. Diagnostic before this pre-registration (training data only, no sealed task): the trained
fields of `transfer_suite.fields()` (math, math_sci, all_sci), `meaning_judge.fields()` (trained,
words_only) and `roles_judge.fields()` are byte-identical with the switch on and off under
`PYTHONHASHSEED=0` (unguarded LET2 changed the meaning and roles fields through 4 training hits).

### No leakage

The guard reads only `task.inputs` and the public + challenge rows; search receives a task view with
`final=()` (INTEGRITY defect 3), and `tests/test_agree.py::test_decision_never_reads_final` checks that
poisoned final rows give an identical decision. The distinguishing inputs carry no expected outputs.

### Controls (judge only)

- `NOMAD_AGREE_CONTROL=shuffled`: each alternative's outcomes are compared on the wrong distinguishing rows
  (rotated by one), so agreement no longer means anything.
- `NOMAD_AGREE_CONTROL=rewired`: each alternative's outcomes are compared with the hit's on rows whose int
  inputs are rotated (each takes the next int input's value) and incremented by one: agreement on the
  wrong question. (A first version only rotated; on a dev suite with symmetric products, e.g. sdev7's
  `a * b * c // 4`, rotation changed nothing and that control kept all support, so the increment was
  added before this pre-registration; no sealed task informed it.)

## Dev (uncommitted dev suites in /workspace/nomad; tuned only there)

Fields: DISCRIM's dev fields (all_sci, practice). Suites: reason_dev (24 two-stage tasks, seeds 11/12),
CEIL's dev catalogue (`ceil_dev`, seeds 31/37: ceilings, the `cl_h_rafts` failure mode), guard suites
(t5dev7, t6dev7, t7dev7, sdev7, sdev11), sci_dev 7/11/13 and the transfer dev list (t2dev7/11, dev7/11/13,
t4dev7, t3dev7).

| dev set (all_sci / practice) | off | unguarded LET2 | AGREE (chosen) | shuffled | rewired | losses (AGREE) |
|---|---|---|---|---|---|---|
| reason + ceil + guard | 94 / 93 | 107 / 107 | **102 / 100** | 94 / 93 | 99 / 97 | 0 |
| sci + transfer dev list | 197 / 178 | - | **198 / 178** | - | - | 0 |

Losses: 0 certification losses and 0 evaluation increases on tasks certified both ways, every dev set.
Unguarded LET2 returned 2 wrong let fits on dev (ceil_dev `cd_o_five`: `(t + 2) // 5` for `ceil(t / 5)`;
t5dev7 `s5_all_handshakes`); AGREE returned none (`cd_o_five` vetoed by the offset quotient `(t + 3) // 5`).
Chosen on dev, in this order: (1) positive support from the stage's own other fits and the next 8
intermediates only kept 99 / 96 (most correct fits had no independent alternative); (2) adding the value
decompositions found support for `|t - c|` but spurious rivals vetoed it, so the veto became the class
rule (support class strictly larger than the largest rival class): 100 / 96; (3) the offset quotients
supported the correct ceilings `(t + 2) // 3` via `(t - 1) // 3 + 1`: 102 / 100; (4) Occam inside the
agreement class (return the smallest agreeing member): no dev count change, but it made the
words_only meaning training field identical to off (the guard had returned a bloated
`tp // t + t // 3` for an average; the class contains `t // 3`).

Honest expectation, written before measuring: AGREE keeps roughly 60% of unguarded LET2's dev gain, so on
the LET2 sealed suite it is expected to land between 9 and 13 (likely 11-12), not at 13.

## Sealed suite (new, written before any field arm is measured)

`nomad/agree_tasks.py` (24 formulas: 10 plain two-stage, 6 ceilings `ceil(t / k)`, 6 comparison /
remainder traps, 2 one-step controls; domains canal / saltworks / kiteworks, used by no other catalogue;
new int inputs `ga gb gc gd`; family prefix `ag_`), generated once by `scripts/agree_suite.py` (TRANSFER
generator, seed **20270521**, unused: no 2027052x seed appears in docs/, scripts/ or the git log; taken are
20261120-20261231, 20270117, 20270203, 20270209, 20270223, 20270307, 20270331, 20270415, 20270419, 20270507):
`data/deep/agree_suite.json`, sha256 `57c7ad22edaaa560ba3bd487ad8844276c3c7accad0ee8ff68b864af3a6dc0d5`,
1 easy (`ag_ctl_one_step`, never scored), **23 hard** (incl. the control `ag_ctl_one_step2`, which the cold
control did not certify), 0 lookup drops. Only the cold control was run.

Judge: `scripts/agree_judge.py` (budget 10,000; re-executes itself under `PYTHONHASHSEED=0`; arms cold /
empty_off / empty_on; for trained (all_sci, scored), math_sci and practice: off / **on** / let2 (unguarded,
report) / shuffled / rewired). Measured **once**, from a snapshot of the commit that adds this file.

## Pre-registered criteria (all must pass to flip the default, in a separate commit)

All runs pinned to `PYTHONHASHSEED=0`.

1. **It helps:** trained_on - trained_off >= 2 certified on the sealed AGREE suite.
2. **Empty identical:** empty_on equals empty_off on every task (certified and evaluations); cold untouched.
3. **No loss on the sealed suite:** for trained, math_sci and practice, nothing certified off is lost on, no
   task certified both ways needs more evaluations on, nothing becomes newly worse than cold (empty_on
   included).
4. **The agreement carries it:** for each control (shuffled, rewired), summed over the three fields, `on`
   certifies strictly more than the control, or at least as many and the control loses (vs off) a task
   `on` keeps.
5. **Zero per-task losses on every existing judge:** `PYTHONHASHSEED=0 SWITCH=NOMAD_AGREE
   scripts/switch_regress.py run OUT` over all 25 existing judges (learning, transfer1-4, secondary4, text,
   bridge, text_invent, route5, transfer6, selfedit2, text_chain, meaning, inflect, let, textpat, roles,
   combine, ceil, merge, let2, discrim, clause, clause2), **every arm judged** (arms that turn
   `NOMAD_LET2` or `NOMAD_DISCRIM` on are unaffected by construction and are judged too): a loss is a task
   certified off but not on, or certified both with more evaluations on. Zero allowed.
6. **LET2's gain kept (the motivating question):** on the LET2 sealed suite (let2 judge, `trained_off` arm
   with AGREE on) trained certifies >= 11 (off 9, i.e. the usual +2 bar); the count against unguarded
   LET2's 13 is reported.
7. **LOFO** (`agree_judge.py --lofo`): trained_agree total <= 5,883 and worst ratio <= 1.0x; the full test
   suite passes.

Reported, not scored: the unguarded LET2 arm and wrong LET2 returns per arm on the sealed suite; per-judge
certified totals and gains; budgets left at each guard decision (dev only).

Decision rule: all seven -> `NOMAD_AGREE` default ON in a separate commit; otherwise it stays OFF with an
honest write-up here and in `results/agree/`.
