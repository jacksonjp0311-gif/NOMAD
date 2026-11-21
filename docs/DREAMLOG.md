# NOMAD dream journal

`NOMAD_DREAMLOG` (default on) is an observational organ. In sleep, and at a body checkpoint if none has been written for 30 minutes, NOMAD appends one entry to a message board about what the logs actually recorded.

It does not affect search or learning. It never writes the field prior, the scoreboard, or the genome. Turning it off (`NOMAD_DREAMLOG=off`) only stops the journal.

## Where to read it

- Board (human-readable, newest first, last 100 entries): [`feed/DREAMS.md`](../feed/DREAMS.md)
- Append-only log (size-capped, well under 2 MB): `data/dreams/journal.jsonl`

The board header states, and this remains the rule: the prose is composed by NOMAD's own deterministic generative grammar from its evidence, not by a language model, and the entries are reflection, not certified claims. WITNESS and the twin scoreboard remain the only sources of certified fact.

## What an entry is grounded in

Every factual claim is counted from the logs since the previous entry (or a stated window):

- attempts and certifications (scoreboard, and the continuous log when a scoreboard window is empty)
- twin control-versus-field deltas and evaluations saved
- library blocks and certified programs in `data/continuous/world_prior.json`, including a diff against the previous entry's snapshot
- genome / SELFEDIT attempts (accepted, refused, or reverted) in `data/evolution.jsonl`
- failures, held-out probes that still return none, heartbeat gaps, and lease takeovers
- domains and families touched

No number is invented. If the logs are quiet, no entry is written.

## How the prose is written

A content hash of the evidence seeds a small deterministic grammar. The grammar writes:

1. an **observation** of the counts, with ordinary inflection (plurals, agreement, tense)
2. a **reflection** that relates those facts to themes — adapting, surviving, invention, change, limits, what "real" means to a system that only trusts certified evidence, and what being alive could mean for a loop that wakes and sleeps
3. one **open question** carried forward

Phrasing varies with the hash. When a certified primitive is in memory, the grammar may quote it as an image (`x·x`, `(x + y·z)//2`, `s∥s`). An entry may reply to the previous open question when new evidence bears on it.

## Live wiring

- `nomad.continuous.sleep` (treatment only) calls `dreamlog.safe_publish`.
- `nomad.body` checkpoints call it if due (30-minute rate limit). The call is wrapped in `try/except` so a journal failure cannot crash the body.
- The body's checkpoint commit already includes `data/` and `feed/`, so the journal and the board travel with the field. The fallback `continuous-sleep` workflow also adds `feed/`.

Manual: `python -m nomad.dreamlog publish` (or `seed --count 3` to rebuild historical samples, `due`, `render`, `gather`).
