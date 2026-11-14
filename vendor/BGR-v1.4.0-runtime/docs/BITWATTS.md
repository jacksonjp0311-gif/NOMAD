# Computational accounting

This release records elapsed process CPU seconds, wall-clock seconds, peak process resident memory, and implementation counters. The full benchmark includes constructing each model, every prediction, every observation update, discovery work, and activation replay.

The scoring optimizations keep inherited logical counters comparable. New counters record actual score computations, cache reuse and cache-entry peaks. A logical candidate evaluation can therefore reuse a previously computed value; it is not necessarily a newly executed scalar scoring loop.

`BitWatts` remains the project's accounting terminology. **This release has no instrumented physical watt or joule measurements.** CPU time is not electrical energy. No energy-saving percentage is reported.

The lag score cache has a configurable entry cap. Total retained history, packed masks and weighted terms still grow with stream length. The grammar cache is local to the current evidence epoch. Neither mechanism is a process-wide CPU or RAM limit.

Peak RSS is measured at the whole subprocess level, including Python and imported models. It is not isolated model weight size. The benchmark reports that scope and preserves all repetitions, including any memory increase.
