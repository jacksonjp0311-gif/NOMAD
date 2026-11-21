# LIVE_WORDS: word problems in the live body's curriculum

MEANING (docs/MEANING.md, default ON) can only learn its lexicon from receipts of tasks that carry
words, and until now no live task did, so the running body never grew its word -> concept links.
`NOMAD_LIVE_WORDS=on` adds the 72 MEANING training word problems, told as stories with their numbers
(`meaning_tasks.train_story_entries`), to the live curriculum as a `words` domain. Code default is
**off** everywhere; the body workflow passes `vars.NOMAD_LIVE_WORDS || 'on'` (like LIVE_BRIDGE), so
the repo variable `NOMAD_LIVE_WORDS=off` turns it off without a commit.

## What changes when on

- `world_tasks.curriculum_train()` gains `words: {1: words_window()}`: a window of 18 word families
  (6 concepts x their 3 domains), rotating every 40 field versions, so all 72 come round in about
  160 learner versions (well inside one body run).
- `curriculum.choose` skips the words domain while word families already make up >= 25% of the
  last 60 world cycles (`WORDS_SHARE`, `WORDS_RECENT`), so word practice cannot starve the 32 other
  families. The first try without this cap spent 72% of cycles on words (below).
- `world_loop.world_pair`: for a word family, the **treatment** gets the story as `words` (MEANING's
  stage reads it once a lexicon exists); the **cold control never reads words**. A certified
  treatment's packet carries `words`, `out` and `sense_kind`, and the sleep learner
  (`consolidate.py`, unchanged) passes them to `add_witnessed`, which teaches the lexicon from the
  verified receipt only.
- `by_family` / `domain_of` resolve `wt_*` families whatever the switch says now (queued packets
  are still re-attested). `all_training()` (evolve benchmark, feed, every judge) never changes.

Off (code default, or MEANING off): the curriculum is exactly `TRAIN` (+ bridge if on); tested.
No sealed judge uses the live curriculum, so no existing suite can change (none imports it).

## Body smoke (`scripts/live_words_smoke.py`, temp copy of `data/` at main, 450 cycles, learner every 3)

| | off | on |
|---|---|---|
| cycles on other families | 450 | 338 |
| their treatment certified | 448 / 450 (99.6%) | 336 / 338 (99.4%) |
| their control certified | 420 / 450 | 314 / 338 |
| word cycles per 150 | 0 / 0 / 0 | 42 / 33 / 37 (~25%) |
| word treatment / control certified | - | 97 / 69 of 112 |
| word tasks solved by MEANING's stage | - | 58 |
| live lexicon after 450 cycles | 0 tokens | 806 tokens, 28 concepts |
| held-out probes | absdiff, quartic_sum certified; 2 none | identical |
| wall time | 23 s | 49 s |

Honest reading: this is plumbing, not a new capability claim. It makes the live body practise word
problems and grow MEANING's lexicon from its own receipts (in the smoke, 58 word tasks were already
solved through words as the lexicon filled). The other families get ~25% fewer cycles; their
certification rate and the held-out probes did not move in the smoke. Word cycles are slower (0.23 s
vs 0.05 s; the MEANING stage plus harder 4-role tasks). Watch item: the live twin guard (evolve) now
sees word cycles too.
