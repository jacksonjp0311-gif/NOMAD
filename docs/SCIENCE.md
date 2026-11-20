# SCIENCE: the first science problem generator (pre-registered)

`nomad/science.py` turns textbook integer physics, unit conversion and
stoichiometry into WORLD tasks with exactly checkable ground truth.
`scripts/science_suite.py` freezes them (seeded) into
`data/deep/science_suite.json`; `scripts/science_probe.py` measures cold vs
field on it. The 40-task deep suite (`data/deep/deep_suite.json`,
sha256 `da3ae9bf…6fbd`) is not read or changed.

## What a science task is

- Named integer inputs, e.g. `v = u + a*t` has inputs `(u, a, t)`. A physical
  or unit constant the problem states (60 s/min, 1000 m/km, 3600 s/h,
  2 / 32 / 18 g/mol for H2 / O2 / H2O) is a **constant input column**
  (`k`, `c`, `kH`, `kO`, `kW`), the way a textbook problem lists its
  constants. The search still only has the `int` opset and constants 0-3.
- Ground truth from a `fractions.Fraction` function written independently of
  the program tree. A row is kept only if the exact answer is an integer and
  the reference tree, run by the WORLD interpreter, gives the same integer, so
  every division is exact. **No interpreter, DSL, WITNESS or tolerance
  change**: WITNESS stays exact-match.
- 5 public / 3 challenge / 3 final rows; certification is the usual WORLD
  rule (public fit -> WITNESS on challenge -> exact final).
- Tagged `domain: "science"` and `kind` in `kinematics | mechanics |
  physics_units | stoich`. `science.science_tag(task)`, `science.is_science`,
  and `world_tasks.domain_of(family)` (returns `"science"` for these
  families) are the hooks the sensing step keys on.

Catalogue (28 families, fixed before any field arm was measured): kinematics
(`v=u+at`, `at`, `at²/2`, `ut+at²/2`, `u+at/2`, `2ad`, `u²+2ad`, `(v-u)/t`,
`(u+v)/2`, `(u+v)t/2`), mechanics (`m(v-u)`, `mv²/2`, `mu²/2`,
`m(v²-u²)/2`, `IR`, `I²R`, `I²Rt`), units (h:m->min, m:s->s, h:m->s,
h:m:s->s, km/h->m/s, metres at v km/h for t s), stoichiometry for
2 H2 + O2 -> 2 H2O (mol H2, O2-limited mol H2O, H2-limited g H2O, limiting
mol H2O, limiting g H2O).

## Tiering (the deep-suite criterion)

Cold control at 10,000 evaluations, max_size 7: not certified -> sealed
`hard` section; certified -> `easy` (curriculum) section. A hard task is
dropped if an easy family's reference tree with the same signature certifies
it. Science signatures cannot match any WORLD held-out (those are `(x,y)`,
`(s)`, `(xs)`).

## Pre-registered success criteria (written before any field arm was measured)

1. **Determinism**: generating twice with the same seed gives the same
   canonical sha256; `--check` passes on the committed file.
2. **Verifier correctness** (tests): for every suite row the stored answer
   equals the Fraction truth (an integer) and the interpreter's value of the
   reference tree; every reference tree certifies (WITNESS supported and
   final exact); a wrong tree (reference + 1) is rejected; a non-integer row
   is refused by the generator.
3. **All tests green** locally and in CI.
4. **Science suite score** (`scripts/science_probe.py`, budget 10,000,
   max_size 7), arms: cold; cold + case split; **field(main)** = the field the
   body runs (trained on the 16 WORLD families, variation + case split);
   **field + science curriculum** = field(main) further trained on the `easy`
   science families only. Reported: certified/total and evaluations per arm.
   - Bar A (no harm): no hard task where any field arm is worse than cold.
   - Bar B (learning): field + science curriculum certifies **at least 25%**
     of the hard science tasks (same bar as the deep suite).
   - field(main) on hard and all arms on easy are report-only.
5. **No regression**: deep-suite sha unchanged; `casesplit_probe.py` still
   gives LOFO total 5,883 (worst 1.0x) and field 6/40 on the deep suite.
   (No search code is changed, so this must hold exactly.)

Nothing is re-tuned after the measurement below; misses are reported.

## Results (2026-11-20, `python3 scripts/science_probe.py`)

Suite: `data/deep/science_suite.json`, seed 20261121, sha256
`4517167f150ef9cfcff5ae947f82d4bd93b9b6ecf5843c2f2976f7b95d54868d`; 28 families, 14 easy, 14 hard (kinematics 5, mechanics 4,
physics_units 3, stoich 2), 0 dropped by the leakage guard.

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 1. Determinism | same sha twice, `--check` ok | identical sha; regeneration test passes | yes |
| 2. Verifier | Fraction truth = interpreter = stored; wrong tree rejected | 308 rows, 28 reference trees certify, 28 `+1` trees rejected | yes |
| 3. Tests | all green | 331 tests OK (6 skipped), incl. 10 in `tests/test_science.py` | yes |
| 4A. No harm on hard | 0 tasks worse than cold | 0 for every arm | yes |
| 4B. field + science curriculum on hard | >= 25% certified @10k | **0 / 14 (0%)**; cold 0, cold+split 0, field(main) 0; every arm spends exactly 10,000 per task (140,000 total) | **no** |
| 4. Easy (report only) | | cold 14/14 in 23,109 evals; field(main) 14/14 in 23,109; field+science 14/14 in 2,038 (in-sample: it trained on these) | |
| 5. No regression | deep sha, LOFO 5,883, deep 6/40 | sha `da3ae9bf…6fbd`; LOFO 5,883 for all arms, worst 1.0x; deep field 6/40, 0 worse | yes |

Why bar B missed: at 10,000 evaluations the staged field never leaves stage 1.
Stage 1 is the cold search below max_size (identical to the control by
design), and with 3-5 named inputs the size-6 level alone costs more than
10,000, so the science blocks the curriculum taught (`mul(a, t)`,
`add(a, a)`, `mul(k, h)`, `mul(I, R)`, `div(gO, kO)`, ...) are never reached.
Nothing was re-tuned after this measurement.

Post-hoc diagnostic (not pre-registered; same arms at 200,000 evaluations,
default max_size 7): cold certifies 5/14, field + science curriculum 8/14,
including three cold cannot certify at all (`u*t + a*t²/2`, `u² + 2ad`,
h:m:s -> s) and three at 4.7-7.7x fewer evaluations (`at²/2`, `I²Rt`,
h:m -> s). It is also slower than cold on some tasks (e.g. `mu²/2` 60,790 vs
58,385). The one case split it proposed (`water_mol`) fitted the public rows
and WITNESS rejected it.

| family | kind | formula | cold @200k (evals) | field + sci @200k (evals) |
|---|---|---|---|---|
| sci_d_rest | kinematics | `d = a*t^2/2 (from rest)` | yes (73,731) | yes (15,560) |
| sci_displacement | kinematics | `d = u*t + a*t^2/2` | no (162,510) | yes (169,227) |
| sci_vmean_uat | kinematics | `mean velocity = u + a*t/2` | yes (11,016) | yes (14,106) |
| sci_vsq | kinematics | `v^2 = u^2 + 2*a*d` | no (154,082) | yes (24,622) |
| sci_d_uvt | kinematics | `d = (u + v)*t/2` | no (64,940) | no (15,656) |
| sci_ke_v | mechanics | `KE = m*v^2/2` | no (47,068) | no (49,640) |
| sci_ke_u | mechanics | `KE0 = m*u^2/2` | yes (58,385) | yes (60,790) |
| sci_dke | mechanics | `work = m*(v^2 - u^2)/2` | no (154,619) | no (157,007) |
| sci_energy | mechanics | `E = I^2*R*t` | yes (69,510) | yes (12,263) |
| sci_hm_to_s | physics_units | `h:m -> seconds` | yes (119,634) | yes (15,523) |
| sci_hms_to_s | physics_units | `h:m:s -> seconds` | no (200,000) | yes (67,691) |
| sci_dist_m | physics_units | `metres covered at v km/h in t s` | no (125,234) | no (200,000) |
| sci_water_mol | stoich | `mol H2O = min(gH/2, 2*gO/32)` | no (200,000) | no (11,271) |
| sci_water_g | stoich | `g H2O = 18*min(gH/2, 2*gO/32)` | no (200,000) | no (200,000) |

Caveats: this is integer physics with chosen-to-be-exact inputs and stated
constants, solved by program synthesis over `+ - * div mod min max ite`. It
checks that NOMAD can find the formula from examples; it is not scientific
reasoning, units are not typed, and constants are given, not known.
The `easy` numbers for field + science are in-sample. Variation has no probe
inputs for the new signatures, so mutants never run on science tasks.

## Iteration 2: BLOCKPROBE (learned blocks before the cold search finishes)

Diagnosis from the miss above: at 10,000 evaluations the staged field never
leaves stage 1 (the cold re-search below max_size) on 3-5 input science
signatures, so learned blocks are never tried.

Change (`nomad/world.py`, `_staged_gen`, off switch `NOMAD_BLOCKPROBE=off`):
when stage 1 has spent `BLOCKPROBE_TRIGGER x max_eval` evaluations without a
hit and the field holds library blocks for the task's signature, stage 1
pauses once; a probe capped at `BLOCKPROBE_CAP x max_eval` enumerates, on a
copy of stage 1's pools, only combinations containing a library block (sizes
up to max_size); then stage 1 resumes unchanged (then case split, variation,
library stage as before). A task stage 1 solves before the trigger is
untouched, so cheap tasks cost exactly what the control costs. A probe hit
still goes through WITNESS like any program (`via = "blockprobe"`).

Also: `variation.PROBES` now has fixed probe inputs for the eight science
signatures, so variation runs on science tasks (stated constants keep their
stated values). It changed no dev result.

Tuning, on an **uncommitted dev science suite** only
(`python3 scripts/science_suite.py --seed 7 --out /tmp/sci_dev.json`; same
28 formulas, different rows, also 14 hard; caveat: same formulas, so dev and
sealed are not independent problems). field + science curriculum, hard dev
tasks certified @10k:

| trigger \ cap | 0.3 | 0.5 |
|---|---|---|
| 0.2 | 4 | 5 |
| 0.35 | 4 | 5 |
| 0.5 | 4 | 5 |

Guard check on the deep suite (a non-regression guard, used to reject
settings, not to rank them): (0.2, 0.5) drops the deep field to 3/40 (case
split starved of budget); (0.5, 0.3), (0.5, 0.5), (0.35, 0.3) keep 6/40.
Chosen: **trigger 0.5, cap 0.5** (the latest trigger, so the most tasks stay
untouched, with the best dev count). Fixed before the sealed run below. Bars
are unchanged from the pre-registration above.

### Sealed result, iteration 2 (measured once, 2026-11-20, `python3 scripts/science_probe.py`)

| Criterion | Bar | Result | Met? |
|---|---|---|---|
| 4A. No harm on hard | 0 tasks worse than cold | 0 for every arm | yes |
| 4B. field + science curriculum on hard @10k | >= 25% | **4 / 14 (28.6%)** in 121,445 evals; cold 0/14, cold + split 0/14, field(main) 0/14 (140,000 each) | **yes** |
| Easy (report only) | | 14/14 for every arm; cold, cold + split and field(main) all 23,109 evals; field + science 2,038 (in-sample) | |
| 3. Tests | all green | 346 tests OK (6 skipped), incl. `tests/test_blockprobe.py` (5) | yes |
| 5. No regression | | `casesplit_probe.py` output identical to before the change: LOFO 5,883 every arm, worst 1.0x; deep field 6/40, 0 worse; held-outs unchanged | yes |

Certified by the block probe: `at²/2` (6,544 evals), `u + at/2` (5,139),
`I²Rt` (6,172), h:m -> s (5,443), each using a block learned on an easy
family (`mul(a, t)`, `mul(I, R)`, `mul(k, h)`). The probe also proposed a
public-row fit for `(u+v)t/2` that WITNESS rejected. field(main) is
unchanged because it holds no blocks for science signatures. Post-hoc
200k diagnostic (not a bar): cold 5/14, field + science 8/14.

Honest reading: the pass is narrow (4 tasks against a threshold of 3.5).
Dev and sealed share formulas, so the dev tuning was not independent of the
sealed problems. The win is curriculum transfer (easy formulas teach blocks
the hard ones reuse), not the field "knowing physics".
