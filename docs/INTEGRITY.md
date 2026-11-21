# INTEGRITY: evidence-loop defects from an external audit

Credit: these defects were reported by an external audit of the repository that James shared on
Nov 21 2026 (an independent review of the experimental method and the evidence loop; its findings
"Critical defect 1: receipts are not bound to admitted programs", "Critical defect 2: crash
recovery can count evidence twice", "WITNESS's challenge split guides search" and the
`evolve.benchmark()` / `probe_heldout()` note). Each claim was treated as a hypothesis: it was
first reproduced by a failing test in `tests/test_integrity.py` on the unfixed code, then fixed.

These are correctness fixes, not science switches. There is no `NOMAD_*` switch: they are always
on, and they do not change any search decision. All existing sealed judges were re-run before and
after the fixes, and their per-task certified counts and evaluation counts were identical (see
"Judge identity" below).

## Defect 1: a receipt was not bound to the program it admitted

**Claim.** `WorldPrior.add_witnessed()` (`nomad/world.py`) and sleep consolidation
(`nomad/consolidate.py`) checked that a receipt was supported and that its checksum verified, then
learned from a separately supplied tree. They never checked that the tree was the program the
receipt attests.

**Reproduction (pre-fix).** `ReceiptBinding.test_receipt_for_add1_does_not_admit_mul2`:
`certify()` attests `add(x, 1)` on a task. Passing that valid, supported receipt with the tree
`mul(x, 2)` to `add_witnessed` was accepted (no error; `witnessed` 0 -> 1, the wrong program
entered memory). At sleep, `ConsolidateBinding.test_swapped_tree_is_refused_and_logged` swapped a
queued world packet's tree for a different program under the same receipt, and it was applied
(`world_applied` 1). Changing the packet's family to another task was applied too.
`GrammarPrior.add_witnessed()` (`nomad/genesis.py`) had the same gap for GENESIS candidates.

**Fix.**
- A receipt's `transmission_id` is the program hash: `world.program_hash(tree)` = sha256 of the
  standalone tree's JSON (exactly what `certify()` always stamped). `world.check_binding()`
  requires the WORLD witness id, `transmission_id == program_hash(tree)`, and, when the caller
  names it, `receipt.task_id == task_id`. `WorldPrior.add_witnessed(..., task_id=None)` calls it
  before anything is learned and raises `witness.ReceiptMismatch` (a `ValueError`) on a mismatch.
- `GrammarPrior.add_witnessed()` requires `transmission_id == sha256(_render(candidate))`, which
  is what `genesis._witness()` stamps.
- At sleep, a world packet's task is resolved from trusted task data (`world_tasks.by_family`),
  the receipt must be bound to the packet's tree and that task's id, and the learner re-attests the
  tree on the trusted task rows (`certify`): the re-attested receipt hash must equal the packet's
  and the final split must pass. A GENESIS packet's receipt must carry the packet's own task id
  (`continuous-<task>`). Refusals are counted in the sleep report (`receipt_mismatch`,
  `reattest_mismatch`, `unbound_task`), listed under `refused`, and appended to
  `data/continuous/refusals.jsonl`.
- Every in-repo caller already passed the tree and receipt from the same `evaluate()` call, so
  nothing that was admitted before is refused now. Checked on all 104 live-resolvable training,
  bridge and word families: 71 cold-certified packets went through a JSON round trip and sleep
  with 0 refusals. The test fixture in `tests/test_molt_extraction.py` used a receipt attested on
  a different task id ("t-mult") than its packet's task. It now carries the packet's task id.

## Defect 2: crash recovery could count evidence twice

**Claim.** `consolidate()` saved each state file and only then acknowledged the in-flight queue,
and duplicate detection was per call. A crash between the two replays an applied packet.

**Reproduction (pre-fix).** `CrashReplay.test_crash_between_save_and_ack_does_not_double_count`:
one certified world packet; `field_queue.ack` is made to crash once; the next sleep re-reads the
in-flight file and applies the packet again: world `witnessed` 1 -> **2**, no duplicate
rejection.

**Fix.** A sleep is now one atomic commit:
1. All changed state is computed in memory: the GENESIS prior, the world prior, the variation
   state, the Bitwork weight packets (`weights.accumulate_list` / `reinforce_list`, the same rule
   as `accumulate` / `reinforce` on the file; pinned by
   `WeightsInMemory.test_accumulate_list_matches_file_accumulate`), the field version, and the
   **applied-packet ledger** `data/continuous/applied_packets.json` (the last 4,096 processed
   packet ids).
2. Each file is written to `<file>.staged`. A manifest `data/continuous/consolidate.commit.json`
   naming them is written with `os.replace`: this is the commit point.
3. The staged files are moved into place (keeping the same `.prev.json` copies as before), the
   manifest is removed, and only then is the queue acknowledged.

The next sleep first rolls forward any committed manifest (`consolidate.recover()`, idempotent),
then drops replayed packets whose id is in the ledger (reason `already_applied`). Because the
ledger lands in the same commit as the state, a packet is counted exactly once whether the crash
comes before the commit point (nothing changed, the packet is applied on replay), during the
moves (rolled forward), or after them and before the ack (dropped as already applied). Tests:
`test_crash_between_save_and_ack_does_not_double_count`,
`test_crash_mid_commit_rolls_forward_once`, `test_new_packet_after_replay_still_learns`.

**Compatibility.** No snapshot format changed: the ledger is a separate file, so the live
`data/continuous/world_prior.json` (and `prior.json`, `variation.json`) load and re-serialize
byte-identically (`CrashReplay.test_legacy_world_prior_loads`). A missing ledger reads as empty,
which is correct for a queue that was acknowledged before this change. The fallback-sleep path
(`python -m nomad.continuous pair` then `sleep --arm treatment`) was run on a copy of the live
`data/`: 6 packets claimed, 3 world and 3 GENESIS applied, 0 dropped, field version 1540 -> 1541.
The ledger was written and no staged files or manifest were left behind. `.staged` files and the
manifest exist only inside one `consolidate()` call and are git-ignored.

## Judge identity (defects 1 and 2)

All 21 existing judges were run on the pre-fix commit (050ea90) and on the same commit with the
fixes for defects 1 and 2: `learning_judge --no-practice` (deep, science hard including
sci_water_mol, LOFO), transfer1 to transfer4, invent2 `--secondary`, text, bridge, text_invent
(INVENT_TEXT), route (TRANSFER-5), graph (TRANSFER-6), route_cut (TRANSFER-7), selfedit round 2,
text_chain, meaning, inflect, let, textpat (TEXT_ABSTRACT), roles, combine, and ceil. 20 of 21
JSON outputs were byte-identical. LOFO stayed at 5,883 with worst ratio 1.0x.

The ROLES judge differed only in its report-only shuffled arms (for example rs_shaft_trips 69 vs
71 evaluations). Those arms are not deterministic across interpreter runs even without any code
change: two pre-fix runs gave shuffled_1 totals of 6,733 and 6,730. With `PYTHONHASHSEED=0`, the
pre-fix and fixed ROLES outputs are byte-identical. This is the same 69-vs-71 variation the CEIL
result recorded on two report-only shuffled arms. It comes from hash-seed-dependent ordering in
the shuffled-lexicon controls, not from these fixes. Every trained, practice, empty, cold and off
arm was identical in all runs.

## One-off history audit (data/ since the body began)

`git log` was scanned over every committed version of `data/continuous/queue.jsonl` (126
versions, 258 distinct packets: 129 world, 129 GENESIS) and `data/continuous/log.jsonl` (243
versions, 1,550 distinct sleep records, 9,262 applied packet ids).
- Receipt binding: 0 of 258 packets had a tree or candidate whose hash differs from its receipt's
  `transmission_id`, a receipt attested on a different task, or (world) a re-attestation that
  differs.
- Double application: 0 packet ids appear as applied in more than one sleep, and world
  `witnessed` grows by exactly `world_applied` between consecutive sleeps (0 discontinuities).
  So no count correction was needed and none was made.
- Caveat: the queue is committed only when a checkpoint falls between enqueue and sleep, so
  receipts exist in history for 258 of the 9,262 applied packets. Binding was checked on all 258.
