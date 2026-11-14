# Registered plan erratum: binary coordinate count

The source and release seed plan were frozen before the release evaluation. The registered PLAN_V012.json mistakenly lists `binary_state_dimensions: 17`. The actual source-frozen `FEATURE_COORDINATES` contains **15** one-hot positions (2 + 2 + 5 + 2 + 2 + 2), with six positions set per represented state. Dynamic and unknown features cause abstention and are not represented as extra coordinates.

This descriptive count mistake was discovered during the release documentation phase, **after** evaluation. To avoid retroactively rewriting preregistration, the original PLAN_V012.json and FREEZE_V012.json are retained unchanged. The mistake does not affect source, seeds, algorithm, classification outputs, thresholds, gates, or audit. The release materials and tests use the correct number (15).
