# Cellular automata

Local rules on the Bitwork field.

A packet is a neighborhood. Overlap with other packets is the neighbor count. Four integer rules are available:

- majority
- growth
- decay
- stabilize

Sleep can run one rule or try all of them. Packets that fall to zero are dropped. New states are appended with their original receipt.

The field evolves without external input. Twin control measures whether any evolved rule improves public success.

Integer only. No floating-point nets.
