# NOMAD feed

Versioned, hash-chained packets of WITNESS-certified building blocks and scores. Pull `manifest.json` / `latest.json`, then verify before use. Format, verification steps and boundaries: [docs/FEED.md](../docs/FEED.md). Schema: `schema/nomad.feed.packet.v1.json`.

No NOMAD install needed to check a packet: `python3 nomad_feed_check.py latest.json --manifest manifest.json` (stdlib only; hash, chain, rows and blocks; WITNESS re-attestation still needs NOMAD).
