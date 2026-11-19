# Task proposer

Generates the next task from the weight field and recent SIM entries.

If a recent success exists, it proposes a variant. Otherwise it continues from the latest packet. The proposal is recorded with the outcome. Reinforcement still passes through the SIM gate.

The system now asks what to try next. Twin control measures whether the answers improve.
