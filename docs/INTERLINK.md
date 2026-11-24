# NOMAD Interlink

External control surface for the body. Pattern from Pegasus Interlink.

## What it is

An outside agent can inspect organism state, observe events, request control,
and export redacted receipts. Mutations are denied by default. No
self-authorization. Receipts are append-only.

## What it is not

Not a second body. Not a learning system. Not a promotion path. The continuous
loop stays the authority. Interlink is the observer and the gate.

## Tools

| Tool | Access | Notes |
|---|---|---|
| inspect | read | organism.json summary |
| observe | read | recent events |
| control | deny-by-default | restart/kill/promote/edit require NOMAD_INTERLINK_MUTATE=on |
| evidence | read | recent redacted receipts |

## Usage

```bash
python -m nomad.interlink inspect
python -m nomad.interlink observe
python -m nomad.interlink control restart   # denied unless NOMAD_INTERLINK_MUTATE=on
python -m nomad.interlink evidence
```

## Boundary

A receipt cannot grant a mutation. The body must apply any accepted change.
Same-account processes can still alter storage. Hashes are not tamper-proof.
