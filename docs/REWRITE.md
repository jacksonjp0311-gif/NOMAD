# Self-rewrite

Adapted from the self-rewriting algorithm in which a model diagnoses its own failures and makes targeted weight edits without gradients.

In NOMAD the field is sparse binary packets.

Diagnosis compares recent SIM successes against failures and ranks packets by differential presence.
A small count reinforcement is proposed for the highest-differential packet.
The edit is committed only after a positive diagnosis. Twin control still measures the outcome.

The system now rewrites its own field on measured evidence. Integer only.
