# CURRIC: a multi-family concept curriculum (switch OFF; sealed suite and criteria pre-registered)

Status (2026-11-27, ET): code landed with `NOMAD_CURRIC` **default off**. Dev separated real memory from
scrambled memory with zero per-task losses, so the sealed suite and the criteria below are committed
**before** any field arm is measured on it. Measured once, after this commit is pushed.

## Why

MEMIDX (docs/MEMIDX.md) and PRIMREC (docs/PRIMREC.md) found the same limit: the trained field never
certified a concept such as `|a - b|` in more than one task family, so no rule that requires repeated
certification could produce it, and scrambled memory kept pace with real memory. The proposed fix was
the curriculum: present the same idea in several families, and let a concept exist only once it has
been certified in several of them.

## What it is (`nomad/curric.py`)

1. **Generator.** 5 concepts (reference functions of two ints: `|a-b|`, `max(a-b, 0)`, `(a-b)^2`,
   `(a+b) div 2`, `2|a-b|`) x 3 contexts (`pair`: inputs x, y; `pick`: p, q, r with q a distractor;
   `swap`: m, n given in the other order) = 15 WORLD families `cu_<concept>_<context>`, 6 / 4 / 4 rows
   from `random.Random(f"curric:1:<concept>:<context>")`, int opset. Search sees only rows. The
   curriculum is training material only; no judge or sealed suite is drawn from it.
2. **Study (concept memory only).** `curric.study(prior, vs)` searches each family with the field
   (WITNESS certifies on public + challenge rows) and logs each certified program and its composite
   subtrees (size 5-11, at most 2 int variables, renamed to parameters) with the family
   (`prior.curric_log`). **Nothing else in the field changes** (library, programs, operator counts,
   variation state); the judge checks this. Dev reason: training the curriculum into the main memory
   (`_train_loop`) lost a task the switch-off field solved (`nv_o_range3`, see below).
3. **Concepts.** `curric.index` groups logged trees by behavior (fingerprint on fixed synthetic probe
   rows, never a task's rows; two-parameter trees are one concept up to argument order) and promotes a
   class only when it was certified in **at least 3 distinct families** (`FAMILIES = 3`). Any tree shape
   counts. No closure rule: the only source of a concept is repeated certification.
4. **Use.** With the switch on and at least one concept, the concepts go first into MEMIDX's existing
   search stage (`world.memidx_stage`): instances bound to the task's int inputs, residual lookups,
   max / min pairs, one second-order step; funded **only by MERGE's unspent skips**, every fit
   WITNESS-gated, the rejection record restored on a miss. A field with no concept (empty, cold,
   untrained, or every scrambled field on dev) searches exactly as with the switch off (the merged bank
   is requested only when a concept exists).
5. **Persistence.** `snapshot()` carries `curric_log` only when it is non-empty (every other snapshot
   is byte-identical). The live body does **not** study yet (see "Not done").

Controls: `NOMAD_CURRIC_CONTROL=rewired:<seed>` permutes family labels over the logged entries;
`NOMAD_CURRIC_CONTROL=gate1` is the ablation with no multi-family requirement. The content control is
`novel_judge.shuffled`, which now also rewires the concept-memory trees like every other memory slot.

## Dev (uncommitted, `/workspace/nomad/curric_dev`)

Dev suites: MEMIDX's dev catalogue (dv7, dv9; 20 hard each) and the NOVEL catalogue with dev seeds
(novel_d11, novel_d13; 26 hard each). Never the sealed suite below. Budget 10,000, PYTHONHASHSEED=0.

Tuning path (all on dev; certified hard tasks, `off` -> `on`, best of 5 shuffles):

| variant | dv7 | dv9 | d11 | d13 | per-task losses |
|---|---|---|---|---|---|
| curriculum trained into a cached field (`_train_loop`), FAMILIES 3 | 6 -> 16, sh 15 | 6 -> 12, sh 12 | 9 -> 14, sh 15 | 9 -> 13, sh 9 | 1 (nv_o_range3) |
| from scratch, CURRIC on during training | 6 -> 16, sh 10 | 6 -> 14, sh 8 | 9 -> 15, sh 10 | 9 -> 14, sh 10 | 1 (nv_o_range3) |
| same, curriculum last | 6 -> 16, sh 10 | 6 -> 12, sh 8 | 9 -> 14, sh 9 | 9 -> 13, sh 10 | 1 (nv_o_range3) |
| same, 1 round | 6 -> 15, sh 12 | 6 -> 11, sh 9 | 9 -> 13, sh 10 | 9 -> 13, sh 9 | 1 (nv_o_range3) |
| **study into concept memory only (committed)** | 6 -> 14, sh 8 | 6 -> 14, sh 7 | 9 -> 14, sh 10 | 9 -> 13, sh 10 | **0** |
| same, gate1 ablation (no multi-family gate) | 6 -> 14, sh 10 | 6 -> 14, sh 8 | 9 -> 14, sh 11 | 9 -> 13, sh 10 | 0 |

`nv_o_range3` was solved by the switch-off field with a correct program (`port:anchor2`), and lost
once the curriculum entered the main memory: a real cost of training, not a lucky fit. Studying into a
separate concept memory removes it.

Final dev check with the committed judge (`scripts/curric_judge.py --suite ...`, fields trained fresh
from this code):

| dev suite | cold | empty off / on | trained_off | studied_off | **trained_on** | shuffled 1-5 | rewired | gate1 / gate1 shuffled | truly correct on / best shuffle |
|---|---|---|---|---|---|---|---|---|---|
| dv7 (20) | 0 | 4 / 4 | 8 | 8 | **15** | 10 7 7 6 6 | 15 | 14 / 10 8 7 10 10 | 15 / 10 |
| dv9 (20) | 0 | 2 / 2 | 8 | 8 | **14** | 7 7 7 8 7 | 14 | 14 / 7 7 7 9 7 | 14 / 7 |
| novel_d11 (26) | 0 | 1 / 1 | 10 | 10 | **15** | 7 8 9 8 9 | 15 | 15 / 7 8 9 8 9 | 14 / 7 |
| novel_d13 (26) | 0 | 2 / 2 | 10 | 10 | **14** | 5 6 7 8 7 | 14 | 14 / 5 6 7 8 7 | 14 / 8 |

On all four: zero tasks lost, zero tasks costlier, empty_on = empty_off per task, the field is identical
to trained_off apart from the concept memory, and every shuffled field has 0 concepts (so shuffled on =
shuffled off). Studied: 14 of 15 curriculum families certify (`cu_absdiff_swap` does not); concepts:
`max(a-b,0)` (5 families), `(a+b) div 2`, `(a-b)^2`, `|a-b|` (3 each).

What the controls say, honestly:
- **Shuffled** is the content control and the one that separates (+5 / +6 / +6 / +6 over the best shuffle).
- **Rewired** equals real on dev: each concept's entries already come from distinct families, so
  permuting labels rarely drops one below 3. It is uninformative here and is report-only.
- **gate1** shows what the multi-family gate buys: real memory is unchanged, while scrambled fields gain
  up to +4 (dv7 shuffle 4: 6 -> 10) once single-family coincidences may become "concepts".
- The concepts were chosen by the author, aware that the dev catalogues use `|a-b|`; the dev margins
  partly reflect that. The sealed suite uses a catalogue no field arm has ever been measured on.

## Sealed suite (generated by the cold control and memory lookup only)

`scripts/curric_suite.py`, **seed 20271127** (new; seeds used before run through 20270613, 20270803 is
reserved for CERT, 20270917 for MEMIDX), on `scripts/memidx_catalogue.py` (sport / weather / pitch /
stock; committed by MEMIDX, never measured by any field arm). `data/deep/curric_suite.json`, sha256
`69d40493...6e7f`: 30 families, 4 easy (cold certifies), **23 hard**, 3 dropped because a memory or
concept-memory tree certifies them outright (`mx_s_margin1`, `mx_w_high_change`, `mx_p_interval`), so no
hard task is a concept looked up as-is.

## Pre-registered criteria (committed before any sealed measurement; measured once)

`PYTHONHASHSEED=0 python3 scripts/curric_judge.py` on the hash-checked suite, output committed unchanged
as `results/curric/curric_sealed.json`. All must hold to flip `NOMAD_CURRIC` on by default:

1. **C1 real beats scrambled**: `trained_on` certifies >= **+3** over **every** `shuffled_1..5`.
   **C1b** the same on truly correct tasks (certified and right on all 2,000 audit rows).
2. **C2 on beats off**: `trained_on` >= `trained_off` **+3**.
3. **C3 empty identical**: `empty_on` = `empty_off` per task (certified, evaluations, via); cold untouched.
4. **C4 no sealed task lost**: none certified by `trained_off` and not by `trained_on`; none certified by
   both with more evaluations on; neither `trained_on` nor `empty_on` worse than cold.
5. **C5 zero per-task losses on every existing judge**, switch on vs off, every arm
   (`SWITCH=NOMAD_CURRIC scripts/switch_regress.py`, all judges in `switch_regress.JUDGES`).
6. **C6 LOFO total 5,883, worst 1.0x**; the full test suite passes.

Reported, not scored: `studied_off`, `rewired`, `gate1` and its shuffles, `shuffled_*_off`, per-domain
counts, the concept list, the audit table, the easy section.

Decision rule: C1-C6 all hold -> default ON in a separate commit; otherwise it stays OFF with an honest
write-up here and in `results/curric/`. If C1-C4 fail, C5 / C6 are not run.

## Not done (scope of this push)

- The live body never studies: with the switch on, only a field that ran `curric.study` has concept
  memory. Wiring it into the body (study once per field version, persisted through the snapshot) is the
  next step if the seal passes.
- String / list contexts: in the current opsets `|a-b|` over two string lengths is size 11 and out of
  the training search's reach, and the list opset has no int `max`; only int contexts are used.

## Switch off = old behavior

With `NOMAD_CURRIC` off: `study` and `record` return immediately, `index` is never called by search,
`port_bank` asks for the merged bank exactly as before, snapshots are unchanged. Tests:
`tests/test_curric.py`.
