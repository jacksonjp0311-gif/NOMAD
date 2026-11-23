# Plan v3 — from the Phase C measurement

## Result

`data/abstract_measure.json`:

- absdiff: fit, `abs((x-y))`, 18 evaluations
- median: no fit, frontier exhausted at 262
- clamp: fit, `min(x,y)`, 6 evaluations

Abs and Min are sufficient for two targets. Median requires comparison or conditional structure the extended grammar does not have.

## What this means

The synthesizer can reach absdiff and clamp when Abs and Min are available. It cannot reach median with the current extended set. That is a measured boundary, not a failure of the measurement.

## Next moves

1. **Promote Abs and Min into the measurement path only.** Do not add them to the continuous loop. Add them as optional operators in a sealed comparison so the field arm can attempt absdiff and clamp on held-out families. Record whether the field certifies them where cold cannot.

2. **Diagnose median.** The frontier exhausted. Median of two numbers is not a closed form over Abs, Min, Max, Sub without a third value or a comparison. Either supply a third argument, or add a comparison operator and remeasure. Do not claim median is unreachable until the comparison form is tested.

3. **Do not wire into the body.** The continuous loop is reinforcing science. Adding operators there without a sealed gain changes the field without a measurement. Keep the operators in the measurement workflow until a sealed suite shows a gain.

## Gate

A sealed suite with unused seed. On/off for Abs and Min. Cold, empty, and field arms. Zero per-task losses. At least one additional solve on a family that requires Abs or Min. Median remains open until a comparison form is measured.

## What is not claimed

This does not produce general intelligence. It produces a measured answer to whether Abs and Min improve held-out certification on families that require them, and whether median is reachable with a comparison operator.
