# Domain weight packets

Ten seeded packets for domain bias. Each is a 30-bit contiguous set in the 4096-bit field, disjoint from the others and from the existing cycle packets. Receipts are marked `seeded` so they are distinguishable from learned outcomes.

| Domain | Bits | Operator | Examples |
|---|---|---|---|
| mathematics | 1100–1129 | Mult | mult |
| science | 1200–1229 | Mult | product (mass × accel) |
| language | 1300–1329 | Sub | sub |
| reasoning | 1400–1429 | Mult | mult |
| understanding | 1500–1529 | Add | add |
| problem-solving | 1600–1629 | Mult | mult |
| logic | 1700–1729 | Add | add |
| evidence | 1800–1829 | Add | add |
| coding | 1900–1929 | Mult | mult |
| meta | 2000–2029 | Add | add |

When the proposer names a domain, that domain is the acting domain: operator, public examples, withheld splits, and tool all come from it. Orbit is context only. Seeded packets are priors, not measured skills. Science uses Mult because its examples are products; the earlier Add label did not match the examples.
