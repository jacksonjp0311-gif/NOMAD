# Molt extraction

Source studied: NVIDIA Molt, https://github.com/NVIDIA-NeMo/labs-molt (commit `ec99ae4`, Apache-2.0, Copyright 2026 NVIDIA CORPORATION & AFFILIATES; parts adapted from OpenRLHF, Apache-2.0). A shallow clone was read on 2026-11-19 and then deleted. **No Molt source was copied.** The ideas below were re-implemented from scratch as small pure-Python, CPU-only modules with no dependencies. NOMAD stays transformer-free.

| # | Idea taken | Molt file it came from | Where it lives in NOMAD |
|---|---|---|---|
| 1 | Decoupled actors and one learner joined by a bounded queue | `molt/trainer/rl_trainer.py` (`Queue(maxsize=async_queue_size)`, generator/trainer split) | `nomad/field_queue.py` (`enqueue`, `claim`, `ack`), `nomad/continuous.py` (awake enqueues), `nomad/consolidate.py` (sleep learns) |
| 2 | Policy-version tagging and bounded staleness | `rl_trainer.py` (rollout slots bound how far generation runs ahead), `molt/agents/base.py` (`off_policy_action_lens`) | `field_queue.field_version` / `bump_version`; every packet carries `field_version`; `nomad/staleness.py` `StalenessPolicy` |
| 3 | Off-policy gating modes mask / clip / trunc | `molt/models/loss.py` (`is_correction_mode`), `molt/models/score_centering.py` (`importance_weights`) | `staleness.importance_weight`, `StalenessPolicy.mode` (mask, decay, trunc, clip). Used as a lag discount, not true importance sampling |
| 4 | Rollout id dedup | `molt/agents/base.py` (`Trajectory.rollout_id`) | `packet_id`; learner drops duplicates |
| 5 | Warm resume of finished-but-untrained work | `molt/trainer/rollout/samples_generator.py` (`state_dict` / `load_state_dict`) | `claim` moves queue to `queue.inflight.jsonl`; a crashed sleep's packets are re-read next time |
| 6 | Drop-reason counters | `samples_generator.py` (`rollout/dropped/<reason>`) | `consolidate()` report `dropped` (duplicate, not_treatment, uncertified, bad_receipt, stale, stale_discounted, future_version) |
| 7 | Group baselines registry (GRPO, Dr.GRPO, RLOO, FlashREINFORCE) | `molt/trainer/algorithm/advantage.py` | `nomad/advantage.py` (plain floats) |
| 8 | DAPO dynamic filter and pre-filter pass statistics | `samples_generator.py` (`_filter_group`, `_passes_dynamic_filter`, all-pass / all-fail rates) | `advantage.informative`, `group_stats`, `twin_summary`; reported by sleep as `twin` |
| 9 | Resume from last good checkpoint | `molt/trainer/fsdp/checkpoint.py` (fallback when `latest` is missing or stale) | `consolidate.save_prior_atomic` keeps `prior.prev.json`; `load_prior_safe` falls back current → previous → cold |
| 10 | Force-sync mode (strict on-policy switch) | `rl_trainer.py` (`force_sync_mode`) | `NOMAD_LEARNER=inline` consolidates right after each treatment awake |
| 11 | Complete-group requirement (never train on half a group) | `samples_generator.py` (`incomplete_group`) | `scoreboard.record_arm` pairs only within one `pair_id`; stale or mismatched unpaired rows are discarded to `scoreboard_discarded.jsonl`; `prune_pending` clears rows older than one hour |

## Deliberately discarded

- **Ray, vLLM, NeMo AutoModel, FSDP2, TP/EP/CP, Muon, CPU Adam offload, NCCL, weight refit/broadcast**: GPU cluster machinery. NOMAD runs on free CPU runners and has no neural weights.
- **Token-level contracts** (action masks, log-probs, top-k score centering, MoE routing replay, sequence packing, seqlen balancing): NOMAD has no tokens or sampler distribution.
- **PPO / CISPO / GSPO losses, KL controllers, critic / GAE**: no differentiable policy. The field learns by counting WITNESS-certified programs.
- **ChatAgent / OpenAI and Anthropic session server, LLM-as-judge, VLM utilities, SFT trainer and datasets**: these are language-model surfaces. NOMAD refuses transformers, and a judge model would violate "search and memory never certify; WITNESS certifies".
- **Gymnasium `Env` / `Result` interface**: NOMAD's `SynthesisTask` + `evaluate_task` + WITNESS receipt already is the environment contract; a second interface would be ceremony.
- **HTTP router retry (20 tries, 4xx fatal)**: the workflows already do bounded `pull --rebase` retry; there is no HTTP inference path to retry.
- **Blocking queue backpressure**: GitHub runners cannot block on a slot across jobs, so NOMAD's queue drops the oldest packet on overflow and counts it.

## Honest limits

In the current schedule, awake and sleep are serialized by one concurrency group, so packet lag is normally 0 and the staleness rule rarely fires. It earns its keep when packets survive a failed sleep or if awake is fanned out in parallel. The staleness weight only gates; it does not scale integer counts. None of this adds synthesis capability by itself.
