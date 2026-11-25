# Integer attention readout

A query is a bit set. Keys and values are packets already in the field.
Score is integer overlap. The attended output is the bit-set union of the
top-k packets by score.

It is only a learning measurement if the attended packet certifies a held-out
probe and the plain overlap does not. The body remains the authority.

This is not transformer attention. There are no learned query, key, or value
matrices. The packets are the keys and the values. The query is the probe or
the current task. The measurement is the same twin and the same WITNESS gate.
