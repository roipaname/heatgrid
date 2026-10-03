# Experiment matrix

| Factor          | Levels |
|-------------------|--------|
| Implementation     | sequential, slab_blocking, slab_nonblocking, cartesian_blocking, cartesian_nonblocking |
| Grid               | 500x500, 1000x1000, 2000x2000 |
| Processes          | 1, 2, 4 (4 is intentionally oversubscribed on this 2-physical-core machine) |
| Scenario           | uniform, single_hotspot, multiple_hotspots, gradient |
| Trials             | 10 measured (+ 1 warm-up, discarded) |
| Timing             | `MPI.Wtime()` (MPI runs) / `time.perf_counter()` (sequential) |

## Scaling sweep (`backend/run_matrix.py scaling`)

All grid sizes x all process counts x all implementations, scenario held fixed at
`single_hotspot`. This is the data RQ1 and RQ2 are answered from. Sequential is only run at
`processes=1` (its own process count doesn't scale).

## Scenario comparison sweep (`backend/run_matrix.py scenario`)

Fixed grid (1000x1000) and process count (2, or 1 for sequential), varying scenario. Excludes
`single_hotspot` at that exact grid/process point since it's already covered by the scaling
sweep, and kept separate from scaling evidence per the methodology.

## Smoke test (`backend/run_matrix.py smoke`)

Same shape as the scaling sweep's per-grid slice but at a single small grid (500x500) and far
fewer timesteps (20 vs 200), for fast development iteration.

## Full matrix (`backend/run_matrix.py full`)

Scaling sweep + scenario comparison sweep, execution order randomised with a fixed seed
(`ORDER_SEED=7919`).
