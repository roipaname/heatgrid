# HeatGrid: Research Summary of Work, Findings and Lessons

Working notes to feed the final research document. Covers what was built, how it was
measured, what the data shows, what went wrong, and what changed along the way. Every number
below comes from `results/raw/benchmark.csv` (real measured runs) or from re-running
`backend/validate_analytic.py`. Nothing is estimated or filled in.

---

## 1. Project in one paragraph

HeatGrid is a study of how **domain-decomposition shape** (1D slab vs 2D Cartesian) and
**halo-exchange mode** (blocking `Sendrecv` vs non-blocking `Isend`/`Irecv` with overlapped
interior computation) affect the performance of an explicit 2D heat-diffusion solver on a
commodity laptop with only 2 physical cores. The Johannesburg framing is carried by four
synthetic, seeded thermal scenarios (uniform, single hotspot, multiple hotspots, gradient). It is
a computational study of parallel behaviour, not a climate model: no forecasting, calibration or
policy claims are made.

**Research questions**

- **RQ1**: Under which grid sizes and process counts does 2D Cartesian decomposition outperform
  1D slab decomposition at very low process counts (1 to 4, single shared-memory node)?
- **RQ2**: To what extent does non-blocking halo exchange with overlapped interior computation
  reduce runtime relative to blocking exchange, and is any reduction consistent with the
  communication time actually measured?

---

## 2. Methodology

### 2.1 Numerical model

- 2D heat equation on the unit square, explicit FTCS five-point stencil:
  `u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4*u(i,j))`
- Diffusion number `r = alpha*dt/dx^2 = 0.20` (stability limit is 0.25, enforced by
  `check_stability`).
- Double precision, row-major NumPy arrays, two buffers swapped by reference each step (no
  full-grid copies).
- Dirichlet boundaries: the outer ring is baked into both buffers at setup and the update loop
  never touches it, so boundary handling is identical across all five implementations.
- One shared stencil kernel (`backend/heat.py::stencil_update`) is used by every implementation,
  so they differ only in decomposition and communication, never in arithmetic.

### 2.2 Implementations

| Name | Decomposition | Communication | Notes |
|---|---|---|---|
| `sequential` | none | n/a | Speedup baseline. Never imports MPI. |
| `slab_blocking` | 1D horizontal slab | `Sendrecv` | 2 neighbours, contiguous rows |
| `slab_nonblocking` | 1D horizontal slab | `Irecv`/`Isend`, interior update, `Waitall`, boundary rows | Genuine overlap window |
| `cartesian_blocking` | 2D, `Compute_dims` + `Create_cart` | `Sendrecv` x4 | Columns sent with `Create_vector` derived datatype |
| `cartesian_nonblocking` | 2D, as above | 8 non-blocking requests, interior update, `Waitall`, 4 boundary strips | Derived datatype, overlap window |

Key design choices:

- **Speedup baseline is the sequential solver, not MPI with p=1**, so MPI overhead stays visible.
- **Derived datatype for west/east columns**: columns are `local_cols + 2` doubles apart in memory,
  so `MPI.DOUBLE.Create_vector(count, 1, stride)` sends them without manual packing. Committed
  once per run, freed in a `finally` block.
- **No corner exchange needed**: the five-point stencil never reads diagonal halo cells, so N/S and
  W/E exchanges are independent.
- **Process grid is chosen by MPI** (`Compute_dims`): p=2 gives 2x1, p=4 gives 2x2.
- **Remainder rows/cols** are spread over the first ranks by one shared `block_distribute`
  function, used by both decompositions.

### 2.3 Scenarios

Seeded with NumPy `Generator(PCG64)`, fully determined by `(name, seed)`:

| Scenario | Seed | Construction |
|---|---|---|
| uniform | 1001 | constant 0.5 interior |
| single_hotspot | 2001 | background 0.3 + one Gaussian (random centre in [0.35, 0.65], amp 0.3 to 0.7, sigma 0.05 to 0.10) |
| multiple_hotspots | 3001 | background + 4 Gaussians, centres in [0.15, 0.85] |
| gradient | 4001 | `0.3 + ax*x + ay*y`, ax in [0.35, 0.45], ay in [0.15, 0.25] |
| decaying_sine | 5001 | `sin(pi x) sin(pi y)`, zero boundary (analytic validation only) |

Boundary value is 0.3 for all Johannesburg-style scenarios.

### 2.4 Correctness validation (two independent checks)

1. **Cross-implementation, cell by cell**: every MPI configuration is gathered once (outside the
   timed region), reconstructed into global order, and compared against a sequential run with
   the same grid, scenario, seed, `r` and timestep count. Reports max absolute, mean absolute and
   max relative error (denominator `max(|ref|, 1e-12)`). Pass threshold: max abs <= 1e-8 or max
   rel <= 1e-6.
2. **Analytic**: the sequential solver is run on the decaying-sine initial condition and compared
   with the closed form `u = sin(pi x) sin(pi y) exp(-2 pi^2 alpha t)`. This measures true
   numerical error, not just agreement between implementations.

### 2.5 Benchmarking protocol

- Timed region is **only the timestep loop**. Scenario construction, allocation, validation and CSV
  writing are excluded.
- MPI timing: `comm.Barrier()` then `MPI.Wtime()`; reported runtime is the **slowest rank**
  (`reduce(..., op=MPI.MAX)`). Sequential uses `time.perf_counter()`.
- Communication time: accumulated time inside `Sendrecv` calls (blocking), or inside request posting
  plus `Waitall` (non-blocking), also MAX-reduced.
- 1 warm-up run discarded, then 10 measured trials. **Median and IQR** reported, not best time.
- Each configuration runs in its own `mpiexec` process (`run_matrix.py` shells out to
  `run_config.py`). Execution order is shuffled with a fixed seed (`ORDER_SEED = 7919`) to spread
  thermal and frequency-scaling effects.
- 4-process runs are **intentionally oversubscribed** (2 physical cores) and flagged in the
  `oversubscribed` column.
- Failed configurations are recorded with `status=failed` and an error message, never dropped or
  replaced with a made-up number.

### 2.6 Platform

- Intel Core i5-7360U, 2 physical / 4 logical cores, 8 GB RAM, macOS
- Python 3.11, NumPy, mpi4py on **MPICH 4.3.2** (conda-forge environment `mpi`)
- All communication is intra-node shared memory

### 2.7 Experiment matrix

| Sweep | Contents | Status |
|---|---|---|
| Smoke | 500x500, 20 timesteps, all 5 implementations, p = 1, 2, 4 (13 configs) | **Complete** |
| Scaling | 500, 1000, 2000 grids x all implementations x p = 1, 2, 4, single_hotspot, 200 timesteps (39 configs) | **30 of 39 complete** |
| Scenario comparison | 1000x1000, p=2, the other 3 scenarios | **Not run** |

---

## 3. Results

All figures are medians of 10 trials. Speedup `S = T_sequential / T_parallel`, efficiency
`E = S / p`. Rows marked (OS) are oversubscribed.

### 3.1 Correctness: passed, with bit-identical results

- **All 43 recorded configurations have status `ok`; all 42 MPI configurations reported max
  absolute error exactly 0.0** against the sequential reference, for every decomposition,
  communication mode and process count, including the oversubscribed runs.
- This is stronger than the tolerance-based pass criterion. It happens because the stencil has no
  reductions: every cell is computed from the same five inputs with the same operation order
  regardless of which rank owns it, so floating-point results are reproduced exactly. The
  tolerance design is still correct and worth keeping, since a different kernel (for example one
  with a global sum) would not be bit-identical.
- **Analytic validation passed** (re-run for this summary):

| Grid | Timesteps | t_final | L_inf error | Mean abs error |
|---|---|---|---|---|
| 81 x 81 | 50 | 0.00156 | 5.38e-6 | 2.13e-6 |
| 161 x 161 | 200 | 0.00156 | 1.35e-6 | 5.38e-7 |

  Halving `dx` at the same final time cut the error by a factor of **4.0**, which is the expected
  second-order convergence (with `r` fixed, `dt` scales with `dx^2`, so the whole scheme is
  O(dx^2)). This is a good result to report: it shows the solver converges at the theoretical rate,
  not just that it is "close".

### 3.2 Sequential baseline

| Grid | Sequential median (s) | IQR (s) |
|---|---|---|
| 1000 x 1000 | 2.054 | 0.108 |
| 2000 x 2000 | 10.131 | 3.587 |

The 500x500, 200-step sequential run is one of the missing configurations, so speedups at 500x500
cannot yet be computed for the scaling sweep. Note the large IQR at 2000x2000 (35% of the median):
the baseline itself is noisy at this size.

### 3.3 Speedup and efficiency (scaling sweep, 200 timesteps)

**1000 x 1000** (sequential 2.054 s)

| Implementation | p | Median (s) | Comm fraction | Speedup | Efficiency |
|---|---|---|---|---|---|
| slab_blocking | 1 | 2.675 | 0.2% | 0.77 | 0.77 |
| slab_nonblocking | 1 | 2.653 | 0.3% | 0.77 | 0.77 |
| cartesian_nonblocking | 1 | 2.787 | 0.5% | 0.74 | 0.74 |
| slab_blocking | 2 | 2.863 | 39.7% | 0.72 | 0.36 |
| slab_nonblocking | 2 | 1.891 | 10.1% | **1.09** | 0.54 |
| cartesian_blocking | 2 | 2.555 | 34.5% | 0.80 | 0.40 |
| cartesian_nonblocking | 2 | 2.017 | 12.6% | 1.02 | 0.51 |
| slab_blocking (OS) | 4 | 6.066 | 87.9% | 0.34 | 0.08 |
| slab_nonblocking (OS) | 4 | 5.402 | 84.2% | 0.38 | 0.10 |
| cartesian_nonblocking (OS) | 4 | 5.195 | 83.0% | 0.40 | 0.10 |

**2000 x 2000** (sequential 10.131 s)

| Implementation | p | Median (s) | Comm fraction | Speedup | Efficiency |
|---|---|---|---|---|---|
| slab_nonblocking | 1 | 10.031 | 0.1% | 1.01 | 1.01 |
| cartesian_blocking | 1 | 10.230 | 0.1% | 0.99 | 0.99 |
| cartesian_nonblocking | 1 | 10.101 | 0.1% | 1.00 | 1.00 |
| slab_blocking | 2 | 12.054 | 19.6% | 0.84 | 0.42 |
| cartesian_blocking | 2 | 8.748 | 15.9% | **1.16** | 0.58 |
| cartesian_nonblocking | 2 | 9.118 | 0.7% | 1.11 | 0.56 |
| slab_nonblocking (OS) | 4 | 9.246 | 8.5% | 1.10 | 0.27 |
| cartesian_blocking (OS) | 4 | 18.511 | 67.1% | 0.55 | 0.14 |
| cartesian_nonblocking (OS) | 4 | 9.329 | 11.3% | 1.09 | 0.27 |

**500 x 500** (no sequential baseline at 200 steps, raw medians only)

| Implementation | p | Median (s) | Comm fraction |
|---|---|---|---|
| slab_blocking | 1 | 0.379 | 0.5% |
| slab_nonblocking | 1 | 0.337 | 1.1% |
| cartesian_blocking | 1 | 0.897 (IQR 0.418, noisy) | 1.1% |
| cartesian_nonblocking | 1 | 0.384 | 1.7% |
| slab_blocking | 2 | 0.617 | 43.2% |
| slab_nonblocking | 2 | 0.534 | 35.9% |
| cartesian_blocking | 2 | 0.659 | 46.3% |
| slab_nonblocking (OS) | 4 | 4.086 | 95.2% |
| cartesian_blocking (OS) | 4 | 11.688 | 97.7% |

**Headline observations**

- **The best measured speedup is 1.16x** (cartesian_blocking, 2000x2000, p=2). On 2 physical cores
  the ceiling is 2.0x; the achieved efficiency is at most about 58%.
- **At 500x500, adding processes makes things slower.** p=2 is roughly 1.6x slower than p=1, and
  communication takes 36 to 46% of runtime. The problem is too small to amortise exchange cost.
- **Speedup only appears once the grid is large enough**: at 1000x1000 only the non-blocking
  variants beat sequential at p=2; at 2000x2000 three of the four p=2 runs do not lose, and the
  2D variants win.
- **MPI p=1 overhead is visible at 1000x1000** (0.74 to 0.77x of sequential, roughly 30% slower)
  but disappears at 2000x2000 (0.99 to 1.01x). Keeping the sequential baseline separate from
  MPI p=1 (as the proposal required) is what made this visible.

### 3.4 RQ1: 2D Cartesian vs 1D slab

Ratio `T_cartesian / T_slab` at the same communication mode (values below 1 mean 2D is faster):

| Grid | p | Mode | Slab (s) | Cartesian (s) | Ratio |
|---|---|---|---|---|---|
| 500 | 2 | blocking | 0.617 | 0.659 | 1.07 |
| 1000 | 2 | blocking | 2.863 | 2.555 | 0.89 |
| 1000 | 2 | non-blocking | 1.891 | 2.017 | 1.07 |
| 1000 | 4 (OS) | non-blocking | 5.402 | 5.195 | 0.96 |
| 2000 | 2 | blocking | 12.054 | 8.748 | **0.73** |
| 2000 | 4 (OS) | non-blocking | 9.246 | 9.329 | 1.01 |

**Interpretation to write up**

- There is **no uniform winner**. 2D is slower at the smallest grid, mixed at 1000, and clearly
  faster only for blocking exchange at 2000x2000 p=2 (27% faster).
- Important caveat: at **p=2 both decompositions are geometrically 1D**. `Compute_dims(2)` gives a
  2x1 process grid, so "Cartesian" at p=2 is also a horizontal split, just through different code
  (Cartesian communicator, 4 exchange calls, two of which go to `PROC_NULL`, derived datatype
  setup). The differences at p=2 therefore reflect implementation and noise effects rather than
  decomposition shape. This is worth stating plainly in the report.
- The only true 2x2 decomposition is at p=4, which is oversubscribed, so RQ1 cannot be answered
  cleanly on this hardware. The honest conclusion is that **at 1 to 4 processes on 2 cores, the
  theoretical communication-volume advantage of 2D decomposition does not show up as a reliable
  runtime advantage**, consistent with the proposal's expectation that 2D only pays off at higher
  process counts.
- Several of the key RQ1 pairs at p=4 are missing (see section 4.1), so this table is incomplete.

### 3.5 RQ2: Non-blocking vs blocking

| Decomposition | Grid | p | Blocking (s) | Non-blocking (s) | Runtime saved | Blocking comm (s) | Non-blocking comm (s) | Comm reduction (s) |
|---|---|---|---|---|---|---|---|---|
| slab | 500 | 2 | 0.617 | 0.534 | +13.4% | 0.267 | 0.192 | 0.075 |
| slab | 1000 | 2 | 2.863 | 1.891 | **+34.0%** | 1.136 | 0.192 | 0.944 |
| cartesian | 1000 | 2 | 2.555 | 2.017 | +21.0% | 0.880 | 0.254 | 0.627 |
| slab | 1000 | 4 (OS) | 6.066 | 5.402 | +10.9% | 5.334 | 4.548 | 0.787 |
| cartesian | 2000 | 2 | 8.748 | 9.118 | **-4.2%** | 1.391 | 0.067 | 1.323 |
| cartesian | 2000 | 4 (OS) | 18.511 | 9.329 | **+49.6%** | 12.422 | 1.056 | 11.365 |

**Interpretation to write up**

- Non-blocking was **faster in 5 of the 6 matched pairs**, by 11 to 50%.
- **Consistency with measured communication** (the second half of RQ2): in 4 of 6 pairs the runtime
  saved is close to the drop in measured communication time (for example slab 1000 p=2: 0.97 s
  saved vs 0.94 s less comm; cartesian 2000 p=4: 9.18 s saved vs 11.37 s less comm). That is the
  signature expected if the overlap window is hiding exchange latency behind interior computation.
- **The exception is cartesian 2000x2000 p=2**: exposed comm time fell from 1.39 s to 0.07 s, yet
  total runtime rose by 0.37 s. So the hidden communication did not turn into saved time. Likely
  causes: the non-blocking path splits the stencil into 1 interior call plus up to 4 boundary-strip
  calls per step (extra NumPy call overhead and less cache-friendly access), and the blocking IQRs
  are around 0.4 s, so the difference is within noise. This is a legitimate negative result.
- **Measurement caveat**: for non-blocking runs, "communication time" is only the *exposed* part
  (posting plus the time spent blocked in `Waitall`). Transfer time that is overlapped with the
  interior update is, by design, not counted. Blocking `Sendrecv` time also includes time waiting
  for a slower neighbour to arrive, so it mixes transfer cost with synchronisation and load
  imbalance. The two comm numbers therefore do not measure exactly the same thing and should be
  described that way in the report.

### 3.6 Oversubscription (p=4 on 2 physical cores)

- Communication fraction jumps to **83 to 98%** for most p=4 runs at 500 and 1000. When 4 ranks
  share 2 cores, a rank waiting in `Sendrecv`/`Waitall` is mostly waiting for a neighbour that has
  been descheduled, so "communication time" here is really scheduling delay.
- p=4 runs also have much larger IQRs (for example slab_nonblocking 1000 p=4: IQR 2.96 s on a 5.40 s
  median; cartesian_blocking 500 p=4: IQR 4.17 s on 11.69 s), showing unstable timings.
- At 2000x2000 the non-blocking p=4 runs survive oversubscription well (about 1.1x speedup, 8 to 11%
  comm fraction) because each step has enough work for the overlap to absorb scheduling delays.
  The blocking Cartesian p=4 run collapses (18.5 s, 67% comm).
- These results should be reported as **stress/functional evidence, not scaling evidence**, as
  planned.

### 3.7 Why speedup is so limited (discussion points)

- The five-point stencil does very little arithmetic per byte moved, so it is **memory-bandwidth
  bound**. Two cores share one memory system, so doubling cores does not double bandwidth.
- The NumPy kernel `c + r*(n + s + w + e - 4.0*c)` creates several full-size temporary arrays per
  step, adding memory traffic on top of the stencil's own.
- mpi4py adds per-call Python overhead to every exchange; at small grids that fixed overhead is a
  large share of each step.
- On a single node all "communication" is a shared-memory copy, so latency is low but not free, and
  synchronisation costs dominate once ranks are out of step.

---

## 4. Failures, gaps and problems encountered

### 4.1 Incomplete scaling sweep

The background scaling run stopped after 30 of 39 configurations. No failure rows were written, so
the process ended (the session closed) rather than a configuration crashing. Missing:

| Grid | Missing configurations |
|---|---|
| 500 | sequential p=1, slab_blocking p=4, cartesian_nonblocking p=2, cartesian_nonblocking p=4 |
| 1000 | cartesian_blocking p=1, cartesian_blocking p=4 |
| 2000 | slab_blocking p=1, slab_blocking p=4, slab_nonblocking p=2 |

Impact: no 500x500 speedups; several RQ1 and RQ2 pairs are missing (for example slab vs cartesian
blocking at p=4, slab blocking vs non-blocking at 2000 p=2). Recommendation: rerun just these nine
(or rerun the full `scaling` matrix) before final write-up.

### 4.2 Scenario comparison sweep not run

No data yet on whether thermal-field structure changes performance. The expected answer is "no",
since the stencil does the same work regardless of values, but it has not been measured, so it
cannot be claimed.

### 4.3 Stale dashboard data

`frontend/public/data/summary.json` was last exported at 18 rows (it still lists only 500x500 and
reports a "best speedup" from a p=1 smoke run). The CSV now has 43 rows. Run
`python backend/export_json.py` to refresh before taking screenshots for the report.

### 4.4 Environment and tooling problems

| Problem | What happened | Resolution |
|---|---|---|
| Homebrew Open MPI | `brew install open-mpi` started building GCC 16 from source (estimated 30 to 90+ min) | Killed |
| New conda env | `conda create -n heatgrid ... openmpi mpi4py` was slow and ended with exit 144 | Abandoned |
| Existing env | Found a working conda env `mpi` with MPICH 4.3.2 + mpi4py + NumPy | Used for all runs |
| `--oversubscribe` flag | Open MPI flag, rejected by MPICH's Hydra launcher (`unrecognized argument oversubscribe`) | Dropped; MPICH oversubscribes without a flag. Documented in `docs/reproducibility.md` |
| uv vs conda | Docs and `pyproject.toml` describe a `uv` workflow, but the recorded benchmarks were run with the conda env's Python and `mpirun` | Should be stated in the reproducibility section, or re-verified under uv |

### 4.5 Bugs caught during development

- **Slab gather offset bug**: the slab decomposition has no column halo, but the owned-block slice
  initially used a 1-cell offset in both dimensions, which would have shifted every column. Caught
  and fixed before validation (`owned_block` now uses a column halo only for Cartesian).
- **Over-wide N/S exchange** in the Cartesian code initially sent the full padded row including
  unused corner cells. Trimmed to the owned column range.
- Both were found before any recorded benchmark, and the bit-exact correctness results confirm the
  final code.

### 4.6 Known limitations of the current harness

- The CSV `checksum_sum` for MPI runs covers **rank 0's block only**, not the full field (the full
  field is only gathered once, for validation).
- If the largest error were ever non-zero, the harness reports its magnitude but not its location
  (global row/column), which the original spec asked for. Not needed so far since all errors are 0.
- No machine-metadata file (compiler/MPI version, git commit) is written automatically. The git repo
  also has **no commits yet**, so results cannot be tied to a commit hash. Commit before the final
  runs.
- No L2 error in the analytic check; the analytic test also runs to a very short final time
  (t = 0.00156, where the solution has only decayed about 3%). A longer run would be a stronger
  test.
- The IQR helper uses simple index quartiles on 10 samples, which is coarse.
- Every rank builds the full global field before slicing its block (simple, but uses about 32 MB per
  rank at 2000x2000; fine at this scale, would not scale to large grids).
- One reading (cartesian_blocking 500 p=1, 0.897 s with IQR 0.418 s vs about 0.38 s for the other
  p=1 runs) looks like background interference. Worth re-measuring.

---

## 5. Modifications and project history

### 5.1 First attempt (abandoned)

The initial specification (85 sections) called for a **C + MPI** core with a Makefile, a Python
analysis pipeline (pandas/matplotlib), a **Streamlit** dashboard, a 30+ column per-trial CSV
schema, a metadata file, central config layering, shell experiment scripts and an automated report
generator. Work started in C, then:

1. **Language changed from C to Python** (mpi4py + NumPy) at the user's request. The C files were
   deleted.
2. A first Python version was built with heavy structure (dataclasses, config modules, many small
   files). This was judged over-engineered.

### 5.2 Restart with a simpler design

The user supplied an earlier project (`task1_ring.py`, `task2a_summation.py`,
`task2b_integration.py`) as the style reference and asked for a full restart. Changes:

| Original spec | What was built instead | Why |
|---|---|---|
| C + Makefile | Flat Python scripts, mpi4py, NumPy | User requirement; simpler to read and grade |
| Dataclass/config-heavy package | Plain functions in ~10 small modules under `backend/` | Match the reference project style |
| Per-trial 30+ column CSV + metadata file | One row per configuration: 10 raw trial times, median, IQR, comm, errors, checksum, oversubscription, status | Keeps raw trials but stays readable |
| pandas/matplotlib analysis + figure scripts + report generator | `export_json.py` (CSV to JSON) + React dashboard | Backend stays "compute + export" |
| Streamlit dashboard | React (Vite) + Recharts static site reading JSON | User preference |

**Kept exactly as in the proposal**: the five implementations, the FTCS stencil and `r` limit,
Dirichlet boundaries, sequential baseline (not MPI p=1), derived datatype for columns, genuine
overlap window, cell-by-cell and analytic validation, 1 warm-up + 10 trials with median/IQR,
slowest-rank timing, randomised seeded order, oversubscription flagging, failure recording, and the
no-fabrication rule.

### 5.3 Frontend iterations

1. First dashboard: runtime/speedup/communication charts, correctness table, scenario heatmaps,
   explicit "no measured results" empty state.
2. User feedback "looks bland": rebuilt into 5 tabs (Dashboard with KPI tiles, Benchmarks with
   small-multiple charts per grid size, Correctness, **Simulation** with a live in-browser stencil
   animation and interactive decomposition diagram, Scenarios heatmap gallery). More grid sizes
   were added by launching the full scaling sweep.
3. Colour palette: the first warm palette (mint/coral/gold) **failed** the colour-blind-safety
   validator (chroma floor, CVD separation, normal-vision separation). It was replaced with a
   validated 4-colour categorical palette with a fixed series order. Note: this palette includes a
   blue, which departs from the spec's "avoid blue" styling guidance in favour of accessibility.
4. User feedback "no emojis, no em dashes": all unicode icons replaced by a custom SVG icon set
   (`Icons.jsx`), and every em dash in code and docs rewritten as plain sentences.

---

## 6. Successes

- All five implementations work, including 2D Cartesian with a real `MPI_Type_vector` datatype and
  genuine communication/computation overlap.
- **Bit-exact agreement** with the sequential reference across all 42 MPI configurations.
- **Analytic validation shows second-order convergence** (error ratio 4.0 when `dx` is halved).
- A fully reproducible pipeline: fixed seeds, fixed run-order seed, one command per sweep, failures
  recorded, no fabricated values anywhere (the dashboard shows an empty state rather than
  placeholders).
- Clear, reportable empirical answers for RQ2 (non-blocking helps in most cases, and the saving
  usually matches the drop in exposed communication), plus an honest, well-explained answer for RQ1.
- A dashboard that makes the data explorable and includes a teaching-oriented simulation view.

---

## 7. Lessons learned

1. **Keep the code as simple as the research allows.** The over-engineered first version cost time
   and was discarded. Simplicity is about code structure, not about dropping experimental rigour.
2. **Sort out the MPI toolchain first.** Most early time went to package managers. Checking for an
   existing working environment would have saved it. MPICH and Open MPI launchers also differ
   (`--oversubscribe`), so scripts must not assume one.
3. **Validate before you benchmark.** Two indexing bugs were caught only because correctness was
   checked cell by cell before timing anything.
4. **Low process counts do not show textbook scaling.** On 2 cores with a memory-bound stencil, the
   best result was 1.16x. Small grids got slower with more processes. The size of the problem
   matters more than the decomposition shape here.
5. **"2D" at p=2 is not 2D.** `MPI_Dims_create(2)` produces a 2x1 grid, so the decomposition-shape
   question only really starts at p=4, which this machine can only run oversubscribed.
6. **Non-blocking helps, but check it against the comm numbers.** A runtime saving that matches the
   drop in exposed communication is evidence of real overlap; a case where comm dropped but runtime
   did not (Cartesian 2000 p=2) shows overlap is not free.
7. **Define what a timer measures.** "Communication time" means different things for blocking and
   non-blocking exchange, and under oversubscription it mostly measures scheduling delay.
8. **Long runs need to be protected.** The scaling sweep stopped when the session ended; long sweeps
   should run under `nohup`/`tmux` and be restartable per configuration.
9. **Run colour/accessibility checks rather than eyeballing.** The first palette looked fine but
   failed colour-blind separation.

---

## 8. Next steps before the final document

1. Rerun the 9 missing scaling configurations (section 4.1), ideally in a detached session.
2. Run the scenario comparison sweep (`python backend/run_matrix.py scenario`).
3. Make a first git commit and record `git rev-parse HEAD` alongside the results.
4. Re-export JSON and take dashboard screenshots for the report.
5. Optionally: extend the analytic test to a longer final time and add an L2 error; re-measure the
   noisy cartesian_blocking 500 p=1 point; consider a single-core-pinned sequential rerun at
   2000x2000 given its large IQR.
6. Write RQ1 and RQ2 conclusions in the neutral style used above: report the measured medians and
   ratios, and state limitations (2 cores, shared memory, oversubscribed p=4, synthetic scenarios).
