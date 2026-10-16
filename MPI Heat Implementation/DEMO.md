# Prototype demonstration (10 minutes)

Run-sheet for the recording. Every command is run from this folder, in the
`heatgrid` conda environment, and takes seconds. Nothing here is a
performance claim: the performance results come from the full suite in
`results/` (see the README's Results section), not from these single runs.

Before recording:

```bash
conda activate heatgrid
cd "MPI Heat Implementation"
clear
```

Times below are wall-clock on an Apple M1 (8 cores). The full suite in
`results/` was measured on the 2-core i5 in `environment/tested_versions.md`.
Say this on camera, because the demo numbers won't match the paper numbers.

**Dashboard option for steps 1–3:** with `python scripts/demo_server.py`
running (after `npm run build` in `frontend/`), open http://localhost:8000 →
**Live demo**. Each button runs the same commands as below and shows the
exact command line with its raw output, plus a short explanation. Keep a
terminal open next to it for step 4, so the brief's "show actual commands"
is covered either way.

### App showcase in 2–3 minutes

Before recording: start `python scripts/demo_server.py`, open
http://localhost:8000, go to **Live demo**, keep the default input (500×500,
single hotspot, 100 steps, 1 warm-up + 3 trials), and run it once off camera
so everything is warm.

| Time | Do | Say |
|---|---|---|
| 0:00–0:15 | Point at the top card | "This tab runs the submitted D2 programs on this machine and shows each exact command and its raw output." |
| 0:15–0:20 | Click **Run all three** | Compute takes under 10 s in total (about 5 s on the M1), so talk while it runs. |
| 0:20–1:00 | Step 1 appears | "The exact-solution error drops by 4.00 each time dx halves, which is second-order convergence. All four MPI variants on 2 and 4 processes match sequential with error exactly 0, on an odd grid, including a real 2×2 split." |
| 1:00–1:45 | Step 2 | Point at the input chips (grid, scenario and seed, steps), the two commands, `mpiexec -n 2`, `grid=2x1`, and `check vs sequential … 0.0 (ok)`. "Only the time-step loop is timed, and MPI time is the slowest rank's." |
| 1:45–2:30 | Step 3 | "Only the halo exchange changed: blocking vs non-blocking with overlap." Read the % difference and the drop in comm share. "One run shows the effect, and the repeated experiments back it up: non-blocking was faster in all 18 pairs in the full suite." |
| 2:30–3:00 | Optional | Switch "What changes" to **Decomposition** at 4 processes (2×2), or open the **Benchmarks** tab with the paper dataset selected. |

If the server isn't running, the tab shows the command to start it. The
terminal commands below still work as a fallback.

---

## 0. Intro (0:00 to 0:45)

One sentence on the problem: the 2D heat equation, explicit five-point FTCS
stencil, `r = 0.2`. Name the five variants and the two questions: slab vs
Cartesian (RQ1), blocking vs non-blocking halo exchange (RQ2).

## 1. Correctness (0:45 to 2:45)

```bash
python scripts/validate.py          # ~3 s
```

What to say about the output:

- **Part 1: exact solution.** `decaying_sine` has a closed-form solution
  `sin(pi x) sin(pi y) exp(-2 pi^2 t)`. The error is about 1e-4 and drops by
  4.00 each time `dx` halves. That is the second-order convergence FTCS should
  give, so the stencil, boundaries and time stepping are all right.
- **Part 2: MPI matches sequential.** All four MPI variants on 2 and 4
  processes, on an odd 37x53 grid that doesn't split evenly. Max abs error is
  exactly 0, meaning the gathered MPI field matches the sequential one bit for
  bit. 4 processes gives a real 2x2 Cartesian grid, so the column halos
  (vector datatype) are exercised too. Any wrong halo row or column would
  show up as a non-zero error.

Optional, if there's time (8 s): `python tests/run_all.py` runs all 14
tests, including the maximum principle, the fixed boundary and the
invalid-input checks.

## 2. Sequential and MPI on the same input (2:45 to 4:30)

Input: **1000x1000 grid, `single_hotspot` scenario (seed 2001), 100 steps,
r = 0.2, 1 warm-up + 3 trials.**

```bash
python src/heat.py --variant sequential --rows 1000 --cols 1000 --steps 100 --trials 3
mpiexec -n 2 python src/heat.py --variant slab_nonblocking --rows 1000 --cols 1000 --steps 100 --trials 3
```

Point out:

- the MPI process count (`-n 2`) and the process grid in the output (`grid=2x1`)
- `check vs sequential: max abs err 0.0e+00 (ok)`. Every MPI run checks itself
  against sequential before timing anything, and exits with status 1 if they
  differ
- the timer covers only the time-step loop. The reported runtime is the
  slowest rank, and `comm %` is the share of time spent in halo exchange

## 3. Meaningful comparison (4:30 to 6:30)

Change one thing, the communication mode (RQ2), and keep the input the same:

```bash
mpiexec -n 2 python src/heat.py --variant slab_blocking --rows 1000 --cols 1000 --steps 100 --trials 3
```

Compare with the `slab_nonblocking` run from step 2. Non-blocking overlaps the
interior update with the halo transfer, so it should be faster, with a lower
`comm %`. On the M1 test run it was 0.38 s and 17.5% comm (blocking) vs
0.32 s and 10.3% (non-blocking).

Then change the process count and decomposition (RQ1):

```bash
mpiexec -n 4 python src/heat.py --variant cartesian_nonblocking --rows 1000 --cols 1000 --steps 100 --trials 3
```

`grid=2x2` is the first real 2D split. With 2 ranks, Cartesian and slab
produce the same 2x1 split, so RQ1 only starts at 4 ranks.

Say that one run is only a demonstration. The claim comes from the repeated
trials in step 4.

## 4. Reproducibility and results (6:30 to 9:30)

**Show the files (about 45 s).** Open `README.md`, scroll through
"Reproducing the full experiment suite" and "How timing works". Then show
`config/full.json` (54 configurations, 5 trials + 1 warm-up, shuffled order)
and the raw data:

```bash
head -3 results/raw/full_20261006-223528.csv
```

One row per trial, including warm-ups. Each row records the variant, process
count, process grid, grid size, seed, steps, runtime, comm time, error and
checksum. The `.json` next to it has the software versions and git commit.

**Generate a summary and figures from the recorded results (about 1 min).**
This re-runs nothing:

```bash
python scripts/summarise.py results/raw/full_20261006-223528.csv
python scripts/make_figures.py
python scripts/show_results.py
```

`summarise.py` turns 324 raw rows into medians, IQR and speedup against the
sequential baseline. `make_figures.py` rebuilds every paper figure in
`paper/figures/`. Open `paper/figures/fig_rq2_overlap.png` and
`fig_speedup.png`.

**Optional: the whole pipeline end to end (about 20 s).**

```bash
python scripts/run_experiments.py config/quick.json && python scripts/summarise.py --name quick && python scripts/make_figures.py --name quick
```

**State the full-suite results (about 1 min, from `show_results.py`):**

- all 54 configurations matched sequential exactly (err 0)
- RQ2: non-blocking was faster in all 18 pairs (17 to 42% on 2 processes)
- speedup is about 1.0 at best on the 2-core machine (memory-bandwidth-bound
  NumPy stencil)
- RQ1 can't be settled: a real 2x2 split needs 4 ranks, which oversubscribed
  the 2 cores (marked `*`)

## 5. Wrap-up (9:30 to 10:00)

Limitations in one breath: one shared-memory node, oversubscribed 4-rank
runs, NumPy kernel, synthetic scenarios.

---

If something goes wrong on camera: `python src/heat.py --help` lists every
option, and bad input (for example `--r 0.3`) exits with a clear error
instead of producing wrong numbers.
