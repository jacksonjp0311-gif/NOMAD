# Orbit algorithm

Developed from the invariant that geometric structure in learned representations follows relational statistics in the data, not the architecture of the model.

Source invariant: translation symmetry in co-occurrence statistics forces related items into the same orbit even when they never directly co-occur. The structure is collective.

## NOMAD form

NOMAD has no continuous embeddings and no Fourier basis. The invariant is applied to the sparse binary field:

- Two packets are related when their bit sets overlap or when their receipts share an operator.
- A query first finds direct hits by integer overlap.
- It then pulls in packets that relate to those hits, even if the packet does not overlap the query itself.
- This is a one-hop orbit. The field supplies the neighbors; the query does not need to touch them.

Implemented in `nomad/orbit.py`. Used by readout when orbit mode is requested.

## What it is not

It does not invent continuous coordinates. It does not claim the field produces circles or maps. It claims only that relational statistics in the packets can pull related packets into the same readout without direct query overlap.
