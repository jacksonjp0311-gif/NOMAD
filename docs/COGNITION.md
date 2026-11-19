# Bitwork cognition

Routes and decides using the weight packets as the only memory.

- Attend: fixed top-k by integer overlap.
- Decide: score options by total overlap of their packets.
- Learn: reinforce the field on success.

Integer overlap is the attention. No transformers. No floating-point nets. The packets are the weights.
