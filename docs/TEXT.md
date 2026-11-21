# TEXT: a string / language held-out transfer suite (pre-registered)

Phase 3 (B): widen the world to strings. Do learned skills transfer to a
never-trained **language** domain (renaming, casing, slicing, joining,
initials, lengths, mixed string+integer), and do integer and string skills
combine?

## Domain (`nomad/text.py`)

46 families: initials (`F.L.`, upper / lower), joins (`Last, First`,
`first.last`, `F. Last`), casings (shouted / quiet names, reversed names),
slicing (capitalise, title-case a name, rotate, drop first letter), lengths
(string -> int), and mixed string+integer (`rep` copies, staircases). Exact
truth: an independent Python function; a row is kept only when the
reference tree reproduces it. Separators are constant input columns (`sp`
= " ", `dt` = ".", `cm` = ","; the DSL has no string constants). Names are
drawn from fixed vocabularies with seeded mixed casing; 5 public / 3
challenge / 3 final rows. Input names (`fn ln w w2 rep sp dt cm`) are
disjoint from training and from both integer transfer catalogues.

## Building blocks (only what the dev suite showed missing)

Tasks run on a new `text` opset: the WORLD `str` opset plus

- `rest` (drop the first character): dev showed capitalising, title-casing
  and rotating are unreachable without it (no other block yields "all but the
  first letter");
- `mul`, `div` for the mixed string+integer tasks.

`OPSETS["str"]` and every existing task are unchanged (tested); `rest` is
used only by text tasks. The cold control runs the task's opset like any
other task; its code is untouched.

## SPLICE (tried on dev, stays off: `NOMAD_SPLICE`)

The string analogue of PORT's anchor: cut the goal left to right into <= 4
pieces drawn from learned bank blocks and probe pool values (optionally
under an upper / lower wrapper), with at least one learned piece. Dev
(uncommitted, `/workspace/nomad/phase3_dev/text/`, seeds 7 and 11):

- first version (any bank block counts as learned): trained 15/23 vs empty
  0 on seed 7, but the "learned" piece was almost always a renamed block that
  merely re-spells an input (`upper(srev(sp))` = " "); the decomposition
  search, not memory, did the work;
- honest version (a bank block counts only when it adds a value the pools do
  not hold): **no gain** (lang 2/23 with or without).

So SPLICE is a search organ, not learning, and fails this phase's bar
(trained beats empty). It stays **off**; recorded as a negative result.

## Sealed suite (`scripts/text_suite.py`, seed 20261124)

`data/deep/text_suite.json`, sha256
`08a826a38fab20dca5897edaf732db84a68a43ace4ec67386e796ad26cb64a02`:
22 easy (cold certifies at 10k; recorded, never scored), **24 sealed hard**,
lookup guard (every trained arm's memory under every type-preserving
renaming, plus easy twins) dropped none.

## Arms (`python3 scripts/text_judge.py`, budget 10,000, max_size 7)

`cold`; `empty`; `lang` (the 8 WORLD language + coding families);
`math_sci` (report); `all_sci` (all 16 WORLD families + easy science,
"everything"); `all_port_off`; `all_grow_off` (report). GROW on, SPLICE off.

## Pre-registered criteria (committed before any field arm is measured on the sealed suite)

1. **String transfer (primary):** `lang` certifies >= **+3** over `empty`, or
   as many with >= **25% fewer** evaluations.
2. **Everything:** `all_sci` vs `empty`, same bar (reported).
3. **Do integer and string skills combine?** `all_sci - lang` reported; > 0
   is "yes". `math_sci` alone is reported too.
4. **No harm:** no arm worse than cold on any task.
5. Unchanged: deep / science / transfer suites and the cold control; LOFO
   5,883, worst 1.0x; all tests pass.

Expectation stated before measuring (from dev seeds 7 / 11: lang 2 and 3,
math_sci 0, all_sci = lang): a **weak or failing** transfer. The domain and
judge are committed either way; nothing in it is switched on by default
(the `text` opset is only used by text tasks).
