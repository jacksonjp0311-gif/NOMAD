# NOMAD intelligence feed

`feed/` is a shared, versioned, append-only feed of what NOMAD's WORLD field knows, published so other agents (for example agent-colony or locus) can pull it and test it against **their own** controls. NOMAD does not push anything into other repos; consumers pull.

## Layout

| Path | What |
|---|---|
| `feed/manifest.json` | `nomad.feed.manifest.v1`: latest version and every packet's sha256 (the chain is kept even after old files are pruned) |
| `feed/latest.json` | copy of the newest packet |
| `feed/packets/NNNNNN.json` | one immutable packet per publish; the last 48 are kept on disk |
| `feed/schema/nomad.feed.packet.v1.json` | JSON Schema for packets |

## What a packet contains

- `blocks`: library sub-programs (typed ASTs such as `mul(x, x)`, `tail(sort(xs))`). A block is published **only** if it occurs inside a program that WITNESS certified during this publish. Search and memory never publish anything.
- `evidence`: one entry per certified training family: the full task rows (public / challenge / final), the standalone program (library calls inlined), the full WITNESS receipt, and the cold-control cost on the same task and budget, next to the field (treatment) cost.
- `scores`: live twin-pair summaries (world and genesis: pass rates, total control vs treatment evaluations, mean evaluations saved) and the last held-out probe (field vs cold). They are copied as measured and are descriptive, not certified.
- `source`: repo, git commit, field_version, number of witnessed world solutions.
- `prev_sha256` / `packet_sha256`: the hash chain.

## Verifying a packet (consumer side)

1. Recompute `packet_sha256`: sha256 of canonical JSON (sorted keys, separators `,` and `:`) of the packet without `packet_sha256`. Check `prev_sha256` against the manifest.
2. For each evidence entry, run `program` on the shipped rows. Every public, challenge and final row must match.
3. Re-attest with WITNESS (`nomad-witness-world-v1`, deterministic) and compare `receipt_hash`; also check the shipped receipt's own checksum.
4. Check that each block is a subtree of a program listed in its `certified_in`.
5. **Your own control:** add the blocks as primitives in your own search, then compare cost against your own cold search on your own tasks. NOMAD's numbers are NOMAD's; a block is only useful to you if it beats your control.

With NOMAD checked out, run `python -m nomad.feed verify feed/latest.json`; it performs checks 1–4 and exits non-zero on any failure. Publishing self-verifies first and refuses to write a packet that fails.

## Cadence and boundaries

The long-lived body publishes at a checkpoint at most every 4 hours (about 45 KB per packet) and commits `feed/` together with `data/`. Run `python -m nomad.feed publish` to publish manually.

Boundaries: programs are tiny (≤ 7 nodes) over a fixed typed DSL, and they are certified only on frozen rows. A block's value elsewhere is unknown until a consumer measures it against its own control.
