# Domain weight packets

Ten seeded packets for domain bias. Each is a 30-bit contiguous set in the 4096-bit field, disjoint from the others and from the existing cycle packets. Receipts are marked `seeded` so they are distinguishable from learned outcomes.

| Domain | Bits | Operator | Examples |
|---|---|---|---|
| mathematics | 1100–1129 | Mult | mult |
| science | 1200–1229 | Add | add |
| language | 1300–1329 | Sub | sub |
| reasoning | 1400–1429 | Mult | mult |
| understanding | 1500–1529 | Add | add |
| problem-solving | 1600–1629 | Mult | mult |
| logic | 1700–1729 | Add | add |
| evidence | 1800–1829 | Add | add |
| coding | 1900–1929 | Mult | mult |
| meta | 2000–2029 | Add | add |

The bias path prefers any domain packet present in the readout. Its receipt supplies the operator and example family. Learned packets remain the fallback. These are priors, not measured skills.
