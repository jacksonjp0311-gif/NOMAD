# CERT: stronger functional certification (candidate 1) - NOT SEALED, switch OFF

Status (2026-11-22): implemented, **default OFF** (`NOMAD_CERT`), never sealed, never measured on a sealed suite.
Sealed seed 20270803 is reserved and still unused; no sealed suite was generated.

## Idea
Generate distinguishing inputs deterministically inside the evidence's own domain (arithmetic edges: moduli
blocks, hull ends, ties) and veto a fit that breaks properties mined from the evidence rows only (`bound`,
`mod`, `mono`); LET2's early return is kept only when the fit is `verified`. A miss is budget-neutral.
Code: `nomad/cert.py`, hook in `nomad/world.py` (`_WitnessGate` veto in port_body scope, LET2 cert mode),
`nomad/cert_tasks.py`, `scripts/cert_suite.py`, `scripts/cert_judge.py`, `tests/test_cert.py`.

## What the dev suites showed (uncommitted dev suites, seeds 11 and 13; NOT sealed evidence)
- NOVEL `nv_d_round10` lucky fits: vetoed 165/165; reference falsely vetoed 20/3000 (slack b+2).
- Dev judge, trained field: cert on == off (6 vs 6), certified_wrong unchanged (2 vs 2), LET2 unguarded 8,
  so criterion 6 (keep LET2 gain) fails and criterion 1 (gain >= 2 audited) fails.
- Why: on the dev tasks that matter (`cda_spread3`, `cda_stage_ceil` wrong fits; `cda_stage_div_rem`,
  `cda_stage_ceil_sum` LET2 fits) the evidence yields **zero** adoptable properties, so the gate can neither
  veto the lucky fit nor verify the good one. Wrong fits differ from truth in ordering/rounding behavior that
  no bound/residue/monotone property mined from 11 rows can express. Without labels or a competing
  candidate, new inputs carry no information; competing-candidate disagreement is what AGREE tried and failed.

## Pre-registered criteria (for any future sealed attempt)
3-arm judge (cold / empty / trained), switch on/off, shuffled and rewired controls; empty_on == empty_off;
cold untouched; zero per-task losses in solves and zero eval increases on all existing judges; trained
audited gain >= 2 with certified_wrong not higher; LET2 gain kept (on - off >= half of unguarded - off) with
zero losses; controls (shuffled, rewired) must not match on; LOFO 5,883 worst 1.0x; PYTHONHASHSEED=0.

## Verdict
No sealed verdict. Dev says the property language is too weak. Next session should either add a richer
label-free property family (e.g., symmetry/permutation relations mined as output-equality classes across
evidence rows, piecewise-linear regularity of one-input sweeps) and test on dev first, or retire CERT.

## Known weakness found at the end
Evidence whose inputs all share a residue (e.g., all multiples of 3) makes the `mod` property veto the
*true* function on generated inputs off that residue class (false veto on `x -> x + 1`). `mod` must only be
adopted when it is explained by the output structure, not by an input-residue coincidence. Fix before any seal.
