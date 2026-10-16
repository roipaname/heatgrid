# HeatGrid presentation notes (slide-by-slide source material)

All paths are relative to the `MPI Heat Implementation/` folder.

These notes are for building the 8–10 slide deck plus the live demo (10 minutes in
total). Every number here is copied from a file in the repo, and each section
names the file it comes from.

Two rules for the whole deck:

1. **Use only the D2 artefact numbers** (full suite
   `results/raw/full_20261006-223528.csv`). `archive/docs/research_summary.md` describes an
   earlier run of the root `backend/` code (10 trials, scaling sweep only 30 of 39
   done, no scenario sweep). Its numbers are different (for example "best speedup
   1.16x"), so don't put them in the deck.
2. **Anything marked `[YOU]` isn't in the repo.** The SDG target, the literature
   gap and the Johannesburg sources came from your D1 proposal. Copy them from
   there. Don't use my suggestions unless they match what you submitted.

---

## Facts at a glance

| | |
|---|---|
| Title | HeatGrid: MPI heat diffusion with domain decomposition |
| Module | IT18X97 Parallel Programming (from the D2 README), Deliverable 2 artefact. **Check the module code**, since your other module is IT18X57 |
| Name | `[YOU]` |
| Model | 2D heat equation, explicit FTCS five-point stencil, Dirichlet boundaries, r = 0.2 (stable for r ≤ 0.25) |
| Variants | sequential, slab_blocking, slab_nonblocking, cartesian_blocking, cartesian_nonblocking |
| Language / libraries | Python 3.11, NumPy 2.4.6, mpi4py 4.1.2, MPICH 4.3.2, matplotlib 3.11 |
| Experiment machine | MacBook Pro, Intel Core i5-7360U, 2 physical / 4 logical cores, 8 GB RAM, macOS 13 |
| Full suite | 54 configurations × (1 warm-up + 5 trials) = 324 raw rows, 3462 s (58 min) total, 0 failed |
| Correctness | all 54 configurations: max abs error vs sequential = 0.0, all trial checksums identical |
| Best speedup (2 ranks) | 1.01 (2000², both non-blocking variants; 1000² `gradient`, Cartesian non-blocking) |
| RQ2 headline | non-blocking faster in all 18 blocking/non-blocking pairs |
| RQ1 headline | can't be answered on 2 cores (2 ranks gives 2x1 for both; 2x2 needs 4 ranks = oversubscribed) |

---

## Slide 1: Title and project overview

- **Title:** HeatGrid: resource-aware MPI heat diffusion using domain
  decomposition, applied to Johannesburg-style urban heat scenarios
- **Name, module:** `[YOU]`, IT18X97 Parallel Programming
- **One-sentence statement:** "This project investigates how the way a 2D
  heat-diffusion grid is split across MPI processes (1D slab vs 2D Cartesian)
  and how boundary data is exchanged (blocking vs non-blocking with overlap)
  affect runtime on a 2-core laptop."
- Logo: `frontend/public/logo.png` (your own asset)

## Slide 2: Problem, context and motivation

What the repo supports:

- **Problem:** heat diffusion on a grid is a standard stencil computation. Every
  cell is updated from its 4 neighbours each time step, so the work grows with
  grid size × steps, and splitting the grid across processes is the textbook
  way to parallelise it. Splitting it means neighbouring processes have to swap
  boundary ("halo") rows/columns every step, and that is the cost under study.
- **Why parallel computing fits:** each step is data-parallel (every cell
  updates independently from the previous step), and the communication pattern
  is local and regular. That makes it a clean test case for decomposition and
  communication choices.
- **South African relevance (the framing, not the result):** the four
  synthetic scenarios (uniform, one hotspot, several hotspots, gradient)
  represent kinds of thermal structure reported for Johannesburg, such as an
  urban heat island, multiple hotspots and a north-south gradient (`DATA.md`).
  They're **not measured temperatures**. The resource angle is that it runs on
  commodity hardware with no cluster access, which is common for
  students and small research groups.
- **SDG:** `[YOU]`, use the goal and target from your D1. If you need options,
  these are mine and you should check them against your proposal:
  - SDG 11, target 11.b (cities adopting integrated policies for climate
    adaptation and resilience), or SDG 13, target 13.1 (resilience to
    climate-related hazards). This is the urban-heat framing.
  - SDG 9, target 9.5 (enhance scientific research and technological
    capability, particularly in developing countries). This is the
    "HPC on low-cost hardware" angle, and it's probably the most honest fit for
    a decomposition study.
- **Say explicitly:** the project contributes no climate prediction. Any SDG
  benefit is a possible future use of efficient simulation tools, not
  something this study measured.

## Slide 3: Research gap, questions and contribution

- **Gap:** `[YOU]`, from your D1 literature review. A version consistent with
  the repo's framing: decomposition and overlap studies usually target
  clusters with many cores and fast networks. Little is reported about what
  these choices are worth at **1 to 4 processes on one small shared-memory
  machine**, which is the hardware many African students and small groups
  actually have.
- **RQ1:** At 1 to 4 processes on one node, for which grid sizes does a 2D
  Cartesian decomposition beat a 1D slab decomposition?
- **RQ2:** How much does non-blocking halo exchange with interior/halo overlap
  save compared with blocking exchange, and does the saving fit the
  communication time actually measured?
- **Contribution (what you actually delivered):**
  - five implementations sharing one stencil kernel, so they differ only in
    decomposition and communication
  - a reproducible benchmark pipeline (seeded inputs, seeded run order, raw
    per-trial CSV with environment metadata, scripted summary and figures)
  - measured answers for RQ2 and a clearly argued "can't be settled on this
    hardware" for RQ1

## Slide 4: Sequential and parallel design

Sources: `src/heatgrid/core/stencil.py`, `solvers/slab.py`, `solvers/cartesian.py`.

**Stencil (shared by all five):**
```
u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4u(i,j))
```
Vectorised NumPy slices, two buffers swapped each step, boundary ring never
updated.

**Sequential baseline:** one process, no MPI import. This is the speedup
reference, not the 1-rank MPI run, so MPI overhead stays visible.

**Data division (diagram suggestion):**
```
 1D slab (p = 4)            2D Cartesian (p = 4, Compute_dims -> 2x2)
 +----------------+         +--------+--------+
 |   rank 0       |         | rank 0 | rank 1 |
 +----------------+         |        |        |
 |   rank 1       |         +--------+--------+
 +----------------+         | rank 2 | rank 3 |
 |   rank 2       |         |        |        |
 +----------------+         +--------+--------+
 |   rank 3       |
 +----------------+         halos: N/S rows (contiguous)
 halos: N/S rows only              W/E columns (MPI vector datatype)
```
Uneven sizes: the first `n % p` blocks get one extra row/column (`block_range`).

**Communication per step:**
- Slab blocking: 2 × `Sendrecv` (up, down)
- Cartesian blocking: 4 × `Sendrecv` (N, S, W, E). Columns use
  `MPI.DOUBLE.Create_vector(count, 1, stride)`, so there's no manual packing.
- Non-blocking (both): post `Irecv`/`Isend`, **update the interior that doesn't
  need halos**, `Waitall`, then update the edge strips.
- No corner exchange is needed, because the 5-point stencil never reads diagonal cells.
- Edges of the global grid use `MPI.PROC_NULL` neighbours.

**Pseudocode for the non-blocking step:**
```
for step in 1..steps:
    post Irecv for each halo; post Isend for each owned edge
    update interior cells          # overlaps with the transfers
    Waitall
    update edge strips that need halo values
    swap(u_old, u_new)
```

**Synchronisation and timing:** `Barrier` before the timer, `MPI.Wtime()`
around the step loop only, runtime = **max over ranks** (`reduce MPI.MAX`).

## Slide 5: Experimental setup

Sources: `environment/tested_versions.md`, `config/full.json`, `results/raw/full_20261006-223528.json`.

- **Hardware:** Intel Core i5-7360U @ 2.30 GHz, **2 physical / 4 logical cores**,
  8 GB RAM, macOS 13 (x86_64). All communication is intra-node shared memory.
- **Software:** Python 3.11.13, NumPy 2.4.6, mpi4py 4.1.2, MPICH 4.3.2 (Hydra
  `mpiexec`), matplotlib 3.11.1.
- **Inputs:** generated, seeded fields: `uniform` (1001), `single_hotspot`
  (2001), `multiple_hotspots` (3001), `gradient` (4001), plus `decaying_sine`
  (5001), which has an exact solution and is used for validation. No external
  dataset.
- **Scaling sweep:** grids 500², 1000², 2000² × processes {1, 2, 4} × 4 MPI
  variants + sequential, `single_hotspot`.
- **Scenario sweep:** 1000², 2 processes, the other three scenarios.
- **Per configuration:** 200 steps, r = 0.2, 1 warm-up + 5 measured trials,
  median and IQR reported. 54 configurations, run in a shuffled order
  (seed 7919).
- **Timing boundary:** only the time-step loop. Setup, the correctness check
  and I/O are excluded. MPI: `Barrier` + `Wtime`, max over ranks. Sequential:
  `perf_counter`.
- **Correctness measures:** max abs error of the gathered MPI field vs
  sequential (must be ≤ 1e-12, checked before every timed run), trial
  checksums, an analytic error with a convergence ratio, and 14 automated tests.
- **Caveat on the slide:** 4 processes = 4 ranks on 2 cores = oversubscribed.
  These runs are flagged, hatched in the figures, and not used as scaling evidence.

## Slide 6: Working prototype demonstration (live)

Follow `DEMO.md` (commands, what to say, timings). In
short:

1. `python scripts/validate.py`: analytic error 1.167e-4 → 2.916e-5 → 7.289e-6
   (ratio 4.00, second order), and all 4 MPI variants on 2 and 4 ranks give
   error 0.0 vs sequential
2. Sequential vs `mpiexec -n 2 … slab_nonblocking`, both on 1000², `single_hotspot`,
   100 steps
3. Comparison: `slab_blocking` vs `slab_nonblocking` (RQ2), then
   `-n 4 cartesian_nonblocking` (2x2, RQ1)
4. README, `config/full.json`, the raw CSV, then `summarise.py` → `make_figures.py`
   → `show_results.py`

The demo machine is an **Apple M1 (8 cores)**, not the i5 used for the
results. Say so on camera. Demo timings are a functional check, not evidence.

You can also do steps 1–3 from the dashboard's **Live demo** tab (see the
README section "Dashboard"). It runs the same programs and shows each exact
command with its raw output. Step 4 (README, raw CSV, summary and figures) is
still best shown in the terminal.

The dashboard also has an **Extended (Apple M1)** dataset with up to 8
processes. It was measured on a different machine from the paper results, so
don't mix its numbers into the results slides unless you label them clearly
as a separate, M1-only experiment.

## Slide 7 (and 8 if needed): Results and discussion

Sources: `results/processed/full_summary.csv`, `full_rq1.csv`, `full_rq2.csv`,
figures in `paper/figures/`.

**Correctness:** all 54 configurations matched sequential exactly (max abs
error 0.0), and every trial of a configuration ended with the same checksum. The
analytic check shows second-order convergence (error ratio 4.00 per halving of dx).

**Runtime and speedup (single_hotspot, medians, 2 processes = not oversubscribed):**

| Grid | Sequential (s) | Best 2-rank variant (s) | Speedup | Efficiency |
|---|---|---|---|---|
| 500² | 0.597 | cartesian_nonblocking 0.795 | 0.75 | 0.38 |
| 1000² | 2.314 | cartesian_nonblocking 2.673 | 0.87 | 0.43 |
| 2000² | 10.735 | cartesian_nonblocking 10.604 / slab_nonblocking 10.632 | 1.01 | 0.51 |

Figures: `fig_runtime.png`, `fig_speedup.png`.

**Application-specific measure (derived by you from the summary table, not a
column in the CSV):** throughput in million lattice-cell updates per second,
MLUPS = (rows−2)(cols−2) × 200 / median runtime. Sequential: 83 (500²),
86 (1000²), 74 (2000²) MLUPS. Best 2-rank: 62, 75, 75 MLUPS. Two processes
barely add throughput, which is consistent with a memory-bandwidth-bound kernel.

**RQ2: blocking vs non-blocking (`full_rq2.csv`, `fig_rq2_overlap.png`):**
- Non-blocking was faster in **all 18 pairs**: 17–65% faster on 2 processes
  (12 pairs), 40–68% on 4 processes (6 pairs, oversubscribed).
- Saving ÷ blocking comm time ranged from 0.34 to 1.42. In most pairs the saving
  is a fraction of the communication there was to hide, which fits overlap
  hiding part of the exchange.
- **Unexpected:** at 2000² on 2 ranks (1.20 Cartesian, 1.42 slab) and on
  `uniform` slab (1.22) the saving is **larger** than the blocking comm time.
  So blocking costs more than the time spent inside `Sendrecv`. A plausible
  (untested) reason is that ranks wait on each other every step, and that
  cost shows up outside the comm timer.

**RQ1: slab vs Cartesian (`full_rq1.csv`, `fig_rq1_slab_vs_cartesian.png`):**
- At 2 ranks, `Compute_dims` gives **2x1**, the same split as the slab. The
  ratios there (0.62–1.14) are noise and code-path differences, not
  decomposition shape.
- A real 2x2 split exists only at 4 ranks (oversubscribed). There, Cartesian
  was slower in 5 of 6 cases (ratio 0.95–1.86).

**Other findings worth one line each:**
- **Scenarios:** sequential time ranges 2.03–2.46 s across the four scenarios at
  1000². The stencil does the same work regardless, and the bigger MPI spread
  (for example `slab_blocking` 7.11 s on `uniform` vs 3.46 s on `gradient`) is
  measurement noise (`fig_scenarios.png`, `fig_scenario_fields.png`).
- **Outlier, reported as measured:** `slab_blocking`, 1 rank, 2000², median
  62.8 s (range 40.6–92.4 s), vs 11–14 s for the other 1-rank variants.
  Most likely outside load or memory pressure.
- **Noisy baseline:** sequential at 500² had trials from 0.43 to 0.99 s, so
  the "1.27 speedup" of 1-rank MPI there isn't real.

**Why speedup is so low (discussion):** the NumPy stencil does little arithmetic
per byte, so it's memory-bandwidth bound. Both cores share that bandwidth, and
halo exchange adds work on top. That explains a maximum of about 1.0x on 2 cores.

## Slide 9: Limitations, conclusion and future work

**Limitations** (from the D2 README):
- one 2-core machine, so all communication is shared memory and nothing
  transfers to networked clusters
- 4-rank runs are oversubscribed. MPICH ranks busy-poll while waiting, which
  makes them much slower than the core count alone suggests.
- NumPy kernel (temporaries every step, slower than C), but the same kernel is
  used for every variant
- non-blocking "comm time" is only the un-hidden waiting, not the total transfer
- every rank builds the full initial field at setup (fine at 2000², doesn't scale)
- synthetic scenarios, so no claims about real Johannesburg temperatures
- the full-suite metadata records git commit `c37967a` (the initial commit).
  The suite ran on 6 Oct at 22:35, and the artefact was committed as `40bf548`
  at 23:41. The results came from the working copy just before that commit.

**Answers:**
- **RQ1:** not answerable on this hardware. At 2 ranks both decompositions are
  the same 2x1 split, and the only real 2D split (4 ranks) was oversubscribed,
  where Cartesian was mostly slower.
- **RQ2:** yes. Non-blocking with overlap reduced runtime in every measured
  pair (17–65% on 2 ranks). The saving mostly fits within the measured
  blocking comm time, but at 2000² it exceeds it, so blocking also has costs
  outside the comm timer.
- **Overall:** on a 2-core laptop, MPI gives at best about 1.0x over a
  well-written sequential NumPy solver. The communication mode matters much
  more than the decomposition shape.

**Future work (realistic):**
- repeat on a machine with ≥ 4 (ideally 8+) physical cores to actually test RQ1
- replace the NumPy kernel with a compiled one (C, Numba or Cython) so compute
  isn't hidden behind memory traffic
- time the wait/synchronisation separately to explain the cases where the
  saving is greater than the comm time
- distributed initial field (no full copy per rank) for larger grids
- only after that: real Johannesburg land-surface temperature inputs

**Keep separate on the slide:** *Measured:* correctness, runtimes, RQ2
savings. *Possible future benefit:* efficient simulation on cheap hardware
could support urban-heat studies (SDG link), but this project didn't show that.

## Slide 10: References and acknowledgements

`[YOU]`: use the references from your D1 and the D2 paper. These are standard
sources for the tools and methods actually used. **Check each entry's
details before you use it.**

- Message Passing Interface Forum. *MPI: A Message-Passing Interface Standard,
  Version 4.0*, 2021.
- Dalcin, L. and Fang, Y.-L. L. "mpi4py: Status Update After 12 Years of
  Development." *Computing in Science & Engineering* 23(4), 2021.
- Harris, C. R. et al. "Array programming with NumPy." *Nature* 585, 2020.
- Hunter, J. D. "Matplotlib: A 2D Graphics Environment." *Computing in
  Science & Engineering* 9(3), 2007.
- Gropp, W., Lusk, E. and Skjellum, A. *Using MPI*, 3rd ed., MIT Press, 2014.
- Hoefler, T. and Belli, R. "Scientific Benchmarking of Parallel Computing
  Systems." *SC15*, 2015 (median/IQR reporting, repeated trials).
- LeVeque, R. J. *Finite Difference Methods for Ordinary and Partial
  Differential Equations*, SIAM, 2007 (FTCS, stability r ≤ 1/4 in 2D).
- Williams, S., Waterman, A. and Patterson, D. "Roofline: An Insightful Visual
  Performance Model for Multicore Architectures." *CACM* 52(4), 2009 (the
  memory-bandwidth explanation).
- MPICH, https://www.mpich.org (MPI implementation used).
- Johannesburg urban heat island sources: `[YOU]` from D1.
- **Acknowledge:** AI assistance, as declared in your AI-use statement. The
  D2 README lists `AI_USE.md`, but that file isn't in the repo, so add it or
  remove the reference.

---

## Figure checklist (all in `paper/figures/`, PNG and PDF)

| Figure | Use on |
|---|---|
| `fig_scenario_fields.png` | slide 2 or 5 (what the inputs look like) |
| `fig_runtime.png` | slide 7 |
| `fig_speedup.png` | slide 7 |
| `fig_rq2_overlap.png` | slide 7/8 (RQ2) |
| `fig_rq1_slab_vs_cartesian.png` | slide 7/8 (RQ1) |
| `fig_scenarios.png` | slide 8 (optional) |

To regenerate them from the recorded data: `python scripts/summarise.py
results/raw/full_20261006-223528.csv && python scripts/make_figures.py`.

## Don't claim

- any speedup above 1.01 on 2 processes, or the 1.16x from `archive/docs/research_summary.md`
- that 2D decomposition is better (not shown on this hardware)
- 4-process results as scaling evidence (they're oversubscribed)
- anything about real Johannesburg temperatures or climate impact
- that the M1 demo timings support performance conclusions
