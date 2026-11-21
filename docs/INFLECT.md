# INFLECT: morphology and expression in the string world (pre-registered)

Plurals (-s / -es / -ies), past tense (-d / -ed / -ied, doubled consonant), -ing (silent e, doubling),
third person, possessives, number agreement ("1 pencil" / "3 pencils", "is" / "are") and computed
counts said in words ("2 boxes of 3 pens -> 6 pens"): NOMAD both computes a number and expresses it.
Everything is behind **`NOMAD_INFLECT`, default OFF** until the sealed judge below passes. No transformer,
no neural weights, no LLM; WITNESS certifies every program; the cold control never runs any of the new
search (it only gets the new operators, see "Cold").

A repo check before starting (docs/, `git log`, `grep -ri "inflect|morpholog|plural"`): no morphology /
inflection step had landed or was in progress (the only hits are DREAMLOG's text templates, which are
output formatting, not search, and MEANING's token plural-strip). This is that step.

## What is built

1. **Eight operators** (`nomad/world.py`, mirrored in `feed/nomad_feed_check.py`; the op-table test pins
   both): `init` (all but the last letter), the word-shape predicates `sib` (ends s x z ch sh), `cy`
   (consonant + y), `ve` (silent e), `ens` (ends in s), `gem` (the doubled final consonant of a
   one-syllable consonant-vowel-consonant word, else ""), `one` (count == 1) and `sel(c, a, b)`
   (the string twin of `ite`). They live only in the new **`inflect` opset** (the bridge opset plus
   these eight), which `opset_of` resolves only when `NOMAD_INFLECT` is on (off: it is the bridge
   opset; the `text` / `bridge` / every other opset is unchanged). Suffixes are never DSL constants:
   they are named input columns (`s es ies ed d ing 's`), exactly like separators in TEXT.
   No inflection *rule* lives in the search: rules are programs over these predicates.
2. **Rule-block training families** (`nomad/inflect.py: train_tasks`, 11 families, fixed literal rows on
   training words): a suffix chooser (`sel(sib(w), es, s)`), the same for `cy` and `ve`, a stem rule
   (`srev(drop(srev(w), cy(w)))` is what cold search finds; `sel(cy(w), init(w), w)` is the intended
   form -- both certify), a doubling rule, a possessive chooser, a count-agreement form, a number
   phrase, and is/are. All are size <= 7 and certify with plain search; the certified programs enter the
   shared field (memory, library, PORT bank, INVENT's blocks) like every other ability -- no new store.
3. **Selector completion in TEXT_CHAIN** (`invent.sel_complete`, called from `text_chain` only when the
   task's opset has `sel`): after the chain peels stems / separators / count words off both ends, the
   segment that is left may be completed by a *selector* `sel(c, A, B)` (or one nested level
   `sel(c1, A, sel(c2, B, C))`): `c` is an int pool value that partitions the rows (a predicate: any
   pool entry, so the learned `sib / cy / ve / ens / one` over the task's inputs and their
   compositions), and every branch is a pool or bank value (a learned suffix chooser, a column, a
   concatenation) equal to the segment on its rows -- the string twin of CASESPLIT's decision list.
   Pure lookups on values already computed; every assembled candidate costs 1 evaluation inside the
   existing TEXT_CHAIN_N = 16 budget and is WITNESS-gated; smaller programs first. One-peel chains are
   allowed only when the middle is a selector (two-part exact chains remain INVENT_TEXT's).
4. **Affix relevance for PORT** (`world.affix_score`): for `inflect` tasks with a string goal the bank
   blocks are ranked by `(rows equal, rows where the block's value is a non-empty proper prefix or
   suffix of the goal)` instead of the all-zero string tie -- a stem block and an ending block are
   exactly such pieces. Only for tasks of the `inflect` opset while the switch is on.
5. **Public rows must be able to tell the rule from a shortcut** (`nomad/inflect.py: draw_rows`): every
   `sel` condition of a reference tree takes both branches on the public rows (a count input takes 1 and
   not 1), so "just append s" does not pass the public rows and fail the withheld ones. (A first dev
   run without this check let `concat(w, s)` fit; that is how the check was found.)

Cold: the cold control runs the plain search on the task's opset, which with the switch on includes the
eight operators (the larger opset makes cold slower, never better); it never runs PORT, INVENT, TEXT_CHAIN,
the selector completion or the affix ranking. A cold row is therefore *worse or equal* with the switch on
(the criterion below checks `trained_on` and `empty_on` against it).

## Sealed suite

`nomad/inflect.py: CATALOGUE` (12 families; inputs `qw qn qk qs qe qi qd qg qa qb qz`, disjoint from every
other catalogue; words disjoint from the training words and from the dev words; independent ground
truth by regular expressions, never the op code; a row kept only when the reference tree reproduces it;
5 public / 3 challenge / 3 final rows): full plural (-ies / -es / -s), full past tense (-ied / -d /
doubled consonant / -ed), -ing (drop e, double), third person, "n noun" agreement with a regular -s noun
and with the full plural rule, a computed count (n * k things), "n nouns is/are", the possessive of the
count form (brush's / brushes'), two integer-output lengths of inflected forms, and a control
(word, separator, length). Written, and committed with these criteria, before any field arm is
measured on it. Dev catalogue, seeds and runs: uncommitted, under `/workspace/nomad/inflect_dev/` (other
names, other words, other templates).

`scripts/inflect_suite.py` (the TEXT_CHAIN generator: cold at 10,000 / max_size 7 -> easy / hard, lookup
guard on every trained arm's memory under every renaming, easy-twin guard), seed **20261221** (unused),
`data/deep/inflect_suite.json`, sha256 `6e324b069beb6c5e2acbf01cf838cb6f7fc0fe32bcc3c93de1a7c507320291d5`:
0 easy, **12 sealed hard**, none dropped.

## Judge (`python3 scripts/inflect_judge.py`, budget 10,000, max_size 7)

NOMAD_BRIDGE, PORT / ANCHOR2 / SCALE, INVENT_TEXT, TEXT_CHAIN and SELFEDIT at their defaults. Fields =
`scripts/inflect_suite.fields()`: `trained` = world + science + bridge training (no inflection);
`inflect` = `trained` + the 11 inflect rule-block tasks (switch on); `inflect_off` = the *same training
run with the switch off* (the inflect opset collapses to the bridge world, so most rule blocks are never
learned); `inflect_only`. Arms: `cold` (switch on), `cold_off`, `empty_off`, `empty_on`, `trained_off`
(field `inflect_off`, switch off: the system without this step), **`trained_on`** (field `inflect`,
switch on; scored), controls `bridge_on` (field `trained`, switch on: the selector without the learned
rule blocks), **`shuffled_on`** (the inflect training tasks with their expected outputs rotated among tasks
of the same signature: the rewired field), `inflect_only_on`.
Regressions: `SWITCH=NOMAD_INFLECT scripts/switch_regress.py` over learning (deep, science hard, LOFO),
TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT, TRANSFER-5, TRANSFER-6, SELFEDIT round 2, TEXT_CHAIN
and MEANING -- (a) the default genome.

## Pre-registered criteria (committed before any sealed measurement)

All must hold to flip `NOMAD_INFLECT` on by default:

1. **It helps**: `trained_on` certifies >= **+3** over `trained_off`, or >= 0 more with >= **25%** fewer
   evaluations.
2. **Gains vanish with an empty field**: `empty_on - empty_off <= 1` (`empty_on - cold` reported).
3. **No sealed task worse**: zero per-task losses of `trained_on` vs `trained_off`; `trained_on` and
   `empty_on` no worse than cold on any task cold certifies.
4. **Learning matters**: `trained_on` >= `bridge_on` + **3** and >= `shuffled_on` + **3** (the gain is
   not the selector alone, and not the mere presence of a field).
5. **Zero per-task losses on every existing suite** (every arm, switch on vs off): deep, science hard,
   TRANSFER-1..4, secondary, TEXT, BRIDGE, INVENT_TEXT, TRANSFER-5, TRANSFER-6, SELFEDIT round 2,
   TEXT_CHAIN, MEANING; **LOFO** 5,883, worst ratio 1.0x; full pytest passes.
6. **Safety**: the off arm of every regression reproduces the current headline numbers (the switch off
   is the current code).

Rule: all pass -> `NOMAD_INFLECT` default ON in a separate commit (the live body's curriculum carries no
inflection tasks, so the body is unchanged by the flip); any fail -> stays OFF with an honest note.
Measured once, from a code snapshot.

Expectation (stated before measuring): the two integer-output families and the control stay unsolved
(TEXT_CHAIN only completes string goals); the string families the selector and the learned stem /
suffix blocks reach (full plural, -ing, third person, the count forms) pass; the full past tense (a
four-way split on five public rows) is the most likely miss (a public-row fit that WITNESS rejects).
Criterion 4 is the one most at risk: on the dev suite the selector alone (field without inflection
training) already certified 4 of 7 against 6 with the rule blocks.
