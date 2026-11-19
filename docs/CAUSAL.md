# Causal path

Packet readout now changes synthesis decisions.

- High-overlap packets with measured public_correct select an operator bias and an example family (add / sub / mult).
- The preferred operator is boosted in the grammar prior before synthesis.
- The chosen operator order and bias reason are written into the outcome log before the candidate is produced.
- Treatment persists the updated prior so the next cycle starts from the biased state.

This is the first path where the field can alter what is synthesized. It is not yet a demonstrated learning advantage on a held-out task.
