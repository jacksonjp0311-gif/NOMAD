# Orbit algorithm — formal statement

Extractable math for the one-hop orbit. Derived from the invariant that geometric structure follows relational statistics in the data, not the model architecture.

## Invariant

Let items be points in a space. Let co-occurrence or shared outcome define a relation. If the relation is approximately translation-invariant (the strength between $i$ and $j$ depends on a difference, not on absolute position), then related items form orbits under that difference even when direct co-occurrence is absent. The structure is collective: an item can be pulled into an orbit by other items that share the relation with it.

## NOMAD realization

Packets are sparse binary sets over a fixed universe $\mathcal{U} = \{0, 1, \ldots, B-1\}$.

A packet is a triple $p = (S, c, r)$ where $S \subseteq \mathcal{U}$ is the bit set, $c \in \mathbb{N}$ is the count, and $r$ is the receipt.

### Overlap

$$
\omega(p, Q) = |S \cap Q|
$$

Direct readout scores by $\omega(p, Q) \cdot c$.

### Relation

Two packets are related by

$$
\rho(p, q) = |S_p \cap S_q| + \lambda \cdot \mathbf{1}[\mathrm{op}(p) = \mathrm{op}(q)]
$$

where $\mathrm{op}(\cdot)$ is the operator recorded in the receipt (if any) and $\lambda = 2$.

### One-hop orbit

Let $D_k(Q)$ be the $k$ packets with highest $\omega(p, Q) \cdot c$.

The orbit of $Q$ is

$$
\mathrm{Orbit}_k(Q) = D_k(Q) \cup \{ p \mid \exists q \in D_k(Q) : \rho(p, q) > 0 \}
$$

truncated to the first $k$ members after expansion.

A packet enters the readout if it overlaps the query or if it relates to a packet that does. Direct co-occurrence with the query is not required.

### What is preserved

- Integer arithmetic only. No floating-point embeddings.
- No Fourier basis. No continuous coordinates.
- The relation is defined on the field. The query does not invent neighbors.

### What is not claimed

The algorithm does not produce circles, maps, or timelines. It produces a one-hop expansion of the readout under the relation $\rho$. The invariant supplies the reason the expansion is valid: related packets can be pulled into the same result by shared structure even when they do not touch the query.

## Implementation

`nomad/orbit.py` implements $\rho$ and $\mathrm{Orbit}_k$. Awake uses it for context. The constants are $B = 4096$, $k = 8$, $\lambda = 2$.
