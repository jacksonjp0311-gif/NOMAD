# CLAUSE2: one concept per clause, paid only from savings, binding forward too (pre-registered)

CLAUSE (docs/CLAUSE.md, fe71ce6) certified 11 / 16 of its sealed suite against 2 with the switch off
(+9 over shuffled, +7 over rewired, about 65% fewer evaluations) and FAILed only criterion 5: 32 per-task
evaluation increases on COMBINE and ROLES, because a CLAUSE miss spent up to 512 evaluations *before* the
normal search ran. Its misses also showed that "the average of the three ..." stories give their numbers
in the NEXT clause, while CLAUSE only bound backward. CLAUSE2 fixes both. Everything is behind
**`NOMAD_CLAUSE2`, default OFF**. No neural nets, no embeddings, no language model: MEANING's counts and
search, WITNESS-gated, deterministic.

## What is built

- `nomad/clause2.py`. CLAUSE's reading is kept: split the story into clauses, bind each clause's numbers
  to the inputs holding them on the first public row, retrieve one concept per clause with MEANING's
  lexicon, compose `B[slot := A]` over clause pairs in rank order, WITNESS-gated through `consult`
  (challenge rows only). Two changes:
  1. **The ledger: a miss is free by construction.** CLAUSE2 never runs before the normal search. A
     per-task ledger keeps every value already computed on the public rows, keyed exactly by what
     determines it: an input or constant atom, or (operator, the operand value vectors), commutative
     operands in a fixed order. MEANING's stage (unchanged in what it tries and charges) records the node
     values of the instances it runs. The normal search then runs **unchanged**: same order, pools, budget,
     stages and charges. Each candidate still costs it 1 evaluation exactly as off, but when the ledger
     already holds the candidate's value it is read instead of recomputed (`world._staged_gen.level` /
     `atom`, `world._search_gen`), and that computation not done is one **credit**. CLAUSE2 runs in
     lockstep, after each of the normal search's evaluations: it reads ledger values for free and may
     compute a value the ledger does not hold only by spending one credit (each new node value is one
     credit, a WITNESS rejection one credit; at most `CLAUSE2_CAP = 512` per task). Main's later reads of
     values CLAUSE2 computed earn credits back. When the normal search (and the stages synthesize runs
     after it) ends without a fit, CLAUSE2 may spend the credit left. Interval inversion of the outer
     concept uses sibling values bought through the ledger and exact interval arithmetic on them (free,
     like `world._redundant`).
  2. **Forward binding.** A concept named in a clause with fewer quantities than its arity may borrow the
     inputs of the nearest numbered clauses *after* it first, as well as before it (CLAUSE's rule). Both
     pools are candidates, ranked by CLAUSE's arity-gap penalty computed against the clause the pool
     actually borrows from (a clause with no numbered clause before it borrows forward either way, so the
     next clause's count applies). "What is the average of the three loads? They are 12, 15 and 9."
     binds the mean to 12, 15, 9.
- Runs only with NOMAD_MEANING and NOMAD_CLAUSE2 on, a field holding a lexicon, a story that contains
  numbers, and after MEANING's stage (and CLAUSE / COMBINE when those are on, unchanged) missed. Learns
  nothing. Empty field: no lexicon, no ledger. Cold control: never reads words. Off: never runs; the
  hooks are `None` checks and main's code path is the old one.
- `NOMAD_CLAUSE2_CONTROL=rewire` (control): each clause bound to the next numbered clause's inputs.
- `nomad/clause2_tasks.py`, `scripts/clause2_suite.py`, `scripts/clause2_judge.py`,
  `tests/test_clause2.py`; `switch_regress` += `clause2`.

### The budget guarantee (stated precisely)

For every task, with NOMAD_CLAUSE2 on versus off (all else equal):

1. The normal search performs the same sequence of steps, keeps the same pools, and reaches the same
   result at the same reported evaluation count, because every value the ledger supplies equals the
   value the search would have computed (same operator, same operand values; Invalid where it would
   be Invalid), and CLAUSE2 never changes the search's state, order, budget or charges.
2. If CLAUSE2 does not return a program (a **miss**), the task's program, receipt, certification and
   reported evaluations are identical to off. (Test: `test_a_miss_is_identical_to_off`, on a task the
   normal search certifies, where CLAUSE2 spends credit and misses; `test_main_search_is_unchanged_under_the_ledger`.)
3. If CLAUSE2 returns a program (a **hit**), it is returned at the normal search's current count (plus
   MEANING's charge, as off), which is <= off's count for that task; the program is certified by WITNESS
   and the independent final split like any other.
4. Computations actually performed <= evaluations reported: CLAUSE2 spends only credits, and a credit is
   a computation the normal search was charged for and did not perform. (MEANING's recorded run computes
   each node on all public rows, where `run` may stop at the first invalid row; its charge is unchanged.)

What it does **not** guarantee: a hit is a different program than off's later find, so it can in
principle pass WITNESS and fail the final split where off's program would have passed. That would be a
certification loss and criterion 5 counts it.

## Sealed suite

`data/deep/clause2_suite.json`: **seed 20270507** (unused: no seed 2027050x appears in the repo; taken are
20261120-20261231, 20270117, 20270203, 20270209, 20270223, 20270307, 20270331, 20270415, 20270419);
16 hard (the cold control certifies none at 10,000 / max_size 7), 0 easy. Eight sealed composites, each
`B[slot := A]` of two MEANING concepts, none a MEANING, COMBINE, CLAUSE or dev composite:
`cr_avg_left` ((a+b+c)//3 % d), `cr_avg_change` (e - (a+b+c)//3 * d), `cr_mean_round` ((a+b)//2 * c * 2),
`cr_mean_boxes` (ceil((a+b)//2 / c)), `cr_avg_share` ((a+b+c)//3 * d // e), told **forward** (the
"average" clause before its numbers, 10 families); `cr_area_round` (a*b*c*2), `cr_bundle_left`
((a+b)*c % d), `cr_sum_boxes` (ceil((a+b+c) / d)), told **backward** (numbers first, 6 families). Domains
no other suite uses: shipyard, aquarium, bike shop, sawmill, ice rink, beehive, dairy, bookbindery; one
distractor quantity each; inputs `ya..yg` shuffled. Generated by the cold control only; no field arm has
been measured on it when this file is committed.

## Judge (`python3 scripts/clause2_judge.py`, budget 10,000, max_size 7)

Field = `roles_judge.fields()` (never a composite). Arms (NOMAD_MEANING on; ROLES, COMBINE, CLAUSE off
unless named; each task's story as `words`): `cold`; `empty_off` / `empty_on`; `trained_off`;
**`trained_on`** (scored); `shuffled_1..3` (CLAUSE2 on, lexicon words reassigned to random concepts);
`rewired` (CLAUSE2 on, wrong clause binding); report only: `clause_report` (CLAUSE on, CLAUSE2 off),
`combine_report` (COMBINE on, CLAUSE2 off); and per task the trained_on ledger (credits earned / spent).

## Pre-registered criteria (committed before any sealed measurement; measured once)

All must hold to flip `NOMAD_CLAUSE2` on by default:

1. **CLAUSE2 helps**: `trained_on` certifies >= **+3** over `trained_off`.
2. **The concepts and the binding carry it**: `trained_on` >= best shuffled-lexicon control **+3** and
   >= `rewired` **+3**.
3. **Gains vanish with an empty field**: `empty_on` = `empty_off` exactly (certified and evaluations);
   cold untouched.
4. **No sealed task lost**: none certified by `trained_off` and not by `trained_on`, none certified by
   both with more evaluations on; neither `trained_on` nor `empty_on` worse than cold.
5. **Zero per-task losses on every existing sealed suite**, switch on vs off, every arm
   (`SWITCH=NOMAD_CLAUSE2 scripts/switch_regress.py`, all 25 earlier judges, i.e. every judge but
   `clause2`, including COMBINE, ROLES, MEANING, CEIL, MERGE, LET, LET2, INFLECT, TEXT_ABSTRACT, DISCRIM
   and CLAUSE's sealed suite): a loss is a task certified off but not on, or certified both with more
   evaluations on. By the guarantee above, evaluation increases are impossible; certification losses
   (a hit that fails the final split) are possible and count.
6. **LOFO total 5,883, worst 1.0x**; the full test suite passes.

Reported, not scored: the forward (10) and backward (6) subsets separately; `clause_report` and
`combine_report`; the gains on existing judges; credits earned and spent.

Decision rule: all six -> default ON in a separate commit; otherwise it stays OFF with an honest write-up
(docs + `results/clause2/`).

## Dev (uncommitted, `/workspace/nomad/clause2_dev` and CLAUSE's `/workspace/nomad/clause_dev`)

Dev suites: CLAUSE's dev catalogue (bakery / library / farm, seeds 7 and 11; backward stories) and a new
forward catalogue (5 dev composites, 10 families, seeds 7 and 13; "What is the average of the three
...? They are ..."). Never CLAUSE's or CLAUSE2's sealed tasks.

| dev suite | trained_off | trained_on | best shuffled | rewired | clause_report | combine_report |
|---|---|---|---|---|---|---|
| CLAUSE dev, seed 7 (11 hard) | 2 | 7 | 2 | 3 | 7 | 5 |
| CLAUSE dev, seed 11 (10 hard) | 3 | 7 | 4 | 3 | 7 | 5 |
| forward dev, seed 7 (10 hard) | 0 | 9 | 2 | 2 | 3 | 10 |
| forward dev, seed 13 (10 hard) | 1 | 10 | 3 | 4 | 3 | 10 |

empty_on = empty_off and no task lost or costlier on every dev suite. Chosen there: the gap penalty
against the clause the pool borrows from (before: forward pools were ranked with the previous clause's
count, so "the average of the three" lost to a 2-input mean; forward dev 5 -> 9 and 4 -> 10 after the
fix); CLAUSE's numberless-outer rule kept (letting such a clause range over all inputs lifted the rewired
control to 5-6 on CLAUSE's dev); CLAUSE's `K`, `POOL`, `EXT` and map caps unchanged; no forward
penalty. Credits per task on dev were 2-400; a CLAUSE2 hit typically lands within the normal search's
first few evaluations (the composite needs 2-30 new values, the rest is read from MEANING's run), and
some later, once main has earned enough credit.

Honest framing, written before measuring: this is clause-wise retrieval plus search over pairs with an
exact arithmetic filter, paid for by not recomputing values; it is not language understanding. The
stories are templated English written by the same agent as the training stories, with the training
stories' relational wording (`packed into ... of`, `hold ... each`, `there and back`, `average of the`).
COMBINE's whole-story retrieval certified all 20 forward dev tasks, so the forward gain over CLAUSE is a
fix of CLAUSE's binding, not a new capability over COMBINE; COMBINE itself stays off (it failed its own
criterion 5). CLAUSE2's credit is small (it is only what main reads instead of recomputing), so a hit
can wait until main has earned enough.
