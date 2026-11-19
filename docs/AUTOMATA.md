# Cellular automata

Local rules on the Bitwork field.

A packet is a neighborhood. Overlap with other packets is the neighbor count. A simple majority-style rule updates the count. Packets that fall to zero are dropped. New states are appended.

The field can evolve without external input. Twin control still measures whether the evolved field improves public success.

Integer only. No floating-point nets.
