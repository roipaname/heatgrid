# HeatGrid: MPI heat diffusion with domain decomposition

IT18X97 Parallel Programming, Deliverable 2 (implementation artefact).

HeatGrid solves the 2D heat equation on a square grid with an explicit
five-point stencil and compares how the grid is split across MPI processes
and how halo cells are exchanged. It runs on a small shared-memory machine
(a 2-core laptop), which is the resource limit the study is about.

## Research problem

The heat equation `du/dt = alpha * laplacian(u)` on the unit square with fixed
(Dirichlet) boundaries, solved with explicit FTCS:

```
u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4u(i,j)),   r = alpha*dt/dx^2
```

`r = 0.2` throughout (the scheme is stable for `r <= 0.25`).

- **RQ1.** At 1 to 4 processes on one node, for which grid sizes does a 2D
  Cartesian decomposition beat a 1D slab decomposition?
- **RQ2.** How much does non-blocking halo exchange with interior/halo
  overlap save compared with blocking exchange, and does the saving fit
  with the communication time actually measured?

This is a depth-route project. There is one model and two design choices
(decomposition, communication mode), tested over three grid sizes, three
process counts and four initial-condition scenarios.

## Program variants

| Variant                 | Decomposition     | Halo exchange |
|-------------------------|-------------------|---------------|
| `sequential`            | none              | none (baseline, no MPI import) |
| `slab_blocking`         | 1D row slabs      | `Sendrecv` |
| `slab_nonblocking`      | 1D row slabs      | `Isend`/`Irecv`, interior updated while halos are in flight |
| `cartesian_blocking`    | 2D `Create_cart`  | `Sendrecv`, vector datatype for columns |
| `cartesian_nonblocking` | 2D `Create_cart`  | `Isend`/`Irecv` + overlap, vector datatype for columns |

All five call the same NumPy stencil (`src/heatgrid/core/stencil.py`), so
they do identical arithmetic per cell and differ only in decomposition and
communication. Speedup is always measured against `sequential`, not the
1-process MPI run, so MPI overhead shows up in the results.

## Layout

```
README.md
AI_USE.md                AI assistance declaration
DATA.md                  where the input data comes from (generated, seeded)
src/
  heat.py                CLI: runs one configuration (check, warm-up, trials)
  heatgrid/
    core/                stencil.py, scenarios.py, partition.py
    solvers/             sequential.py, slab.py, cartesian.py
    checks.py            field comparison, analytic solution
    records.py           raw CSV columns and writer
tests/                   correctness tests, run_all.py runs them without pytest
scripts/
  run_experiments.py     runs a config, writes raw trial rows
  summarise.py           raw -> medians, IQR, speedup, efficiency, RQ tables
  make_figures.py        processed tables -> paper/figures
  quick_demo.sh          tests + quick config in one go
config/                  quick.json (demo), full.json (paper)
results/raw/             unedited trial-level CSVs + run metadata (.json)
results/processed/       summary and RQ tables made by summarise.py
paper/figures/           every figure used in the paper (PNG + PDF)
environment/             environment.yml, requirements.txt, tested_versions.md
```

## Requirements and install

Tested with Python 3.11, NumPy 2.4, mpi4py 4.1, MPICH 4.3.2 and matplotlib
3.11 on macOS (Intel). Full details are in `environment/tested_versions.md`.

Conda is the easiest route because it installs MPI as well:

```bash
conda env create -f environment/environment.yml
conda activate heatgrid
```

With pip you need an MPI library first (e.g. `brew install mpich` or
`apt install mpich libmpich-dev`), then:

```bash
pip install -r environment/requirements.txt
```

If mpi4py can't find the MPI library (common with mpi4py 4 wheels and MPI
installed through conda), point it at the library:
`export MPI4PY_LIBMPI=$CONDA_PREFIX/lib/libmpi.12.dylib` (or `libmpi.so.12` on
Linux).

All commands below are run from this folder. No paths need editing.

## Correctness tests

```bash
python tests/run_all.py        # about 1 minute, or: pytest tests/
```

What they check:

- the sequential solver against the exact decaying-sine solution, and that
  halving `dx` cuts the error by about 4 (second-order convergence)
- a constant field stays constant, the boundary never changes, and values
  stay within the initial min/max (maximum principle)
- all four MPI variants on 1, 2, 3 and 4 processes, on odd grid sizes
  (37x53, 64x48, 41x41), match the sequential field exactly, and every trial
  ends with the same checksum
- invalid parameters (`r > 0.25`, grids smaller than 3x3, zero steps or trials,
  too many ranks for the grid, `sequential` under `mpiexec -n 2`) exit with a
  clear error and a non-zero status

Each `src/heat.py` run also checks itself before timing anything. It runs the
MPI version once, gathers the field on rank 0, compares it with the
sequential result and exits with status 1 if they differ by more than
`1e-12`. In practice the difference is exactly 0.

## Quick demonstration

```bash
bash scripts/quick_demo.sh
```

This runs the tests and a single sequential and MPI run, then the quick
config: 256x256, 100 steps, 1 and 2 processes, 1 warm-up plus 5 trials.
It takes about 2 minutes. Results go to `results/raw/quick_<stamp>.csv`,
`results/processed/quick_*.csv` and `results/processed/figures_quick/`.

Single runs by hand:

```bash
python src/heat.py --variant sequential --rows 500 --cols 500 --steps 200
mpiexec -n 2 python src/heat.py --variant slab_nonblocking --rows 500 --cols 500 --steps 200
python src/heat.py --help
```

## Reproducing the full experiment suite

```bash
python scripts/run_experiments.py config/full.json
python scripts/summarise.py            # newest results/raw/full_*.csv
python scripts/make_figures.py
```

`config/full.json` has 54 configurations:

- scaling sweep: 500², 1000², 2000² × {1, 2, 4} processes × 4 MPI variants,
  plus the sequential baseline, `single_hotspot`
- scenario sweep: 1000², 2 processes, `uniform`, `multiple_hotspots`,
  `gradient` (`single_hotspot` already comes from the scaling sweep)

All runs use 200 steps, `r = 0.2`, 1 warm-up and 5 measured trials. They run
in a shuffled order (seed 7919) so slow drift such as thermal throttling
doesn't line up with one variant. Use `--dry-run` to print every command
without running anything.

The results in `results/` and `paper/figures/` come from
`results/raw/full_20261006-223528.csv` (run metadata in the matching `.json`).

### How timing works

- Field setup, buffer allocation, the correctness check, CSV writing and
  printing all happen outside the timed region.
- `Barrier()` right before the timer starts, then `MPI.Wtime()` around the
  time-step loop only. The sequential baseline uses `time.perf_counter()`.
- The runtime for a trial is the **maximum** over all ranks (`reduce` with
  `MPI.MAX`). Communication time (time inside `Sendrecv`, or posting
  `Isend`/`Irecv` plus `Waitall`) is reduced the same way.
- Every trial is recorded, warm-up included (`warmup=True`).
  `summarise.py` drops warm-ups and reports the median and IQR.
- Each raw row has the variant, process count, process grid, grid size,
  scenario, seed, steps, `r`, trial number, runtime, comm time, error vs
  sequential, checksum, physical core count and an `oversubscribed` flag.

### Runtime and memory

On the test machine (i5-7360U, 2 cores):

| Run | Time |
|-----|------|
| `tests/run_all.py` | ~1 min |
| quick config | ~15 s (`quick_demo.sh` in total ~2 min) |
| full config | 58 min (3462 s), most of it in the oversubscribed 4-rank runs |

The largest grid (2000²) uses 32 MB per array. The sequential solver peaks at
about 200 MB. Each MPI rank briefly builds the full initial field before
slicing out its block, and rank 0 also holds the gathered field and the
sequential reference during the check. Total memory stays under about 1 GB.

## Results

All numbers below come from `results/processed/full_*.csv`, made by
`scripts/summarise.py` from the raw file above. Medians of 5 trials, 200
steps, `single_hotspot` unless stated.

**Correctness.** All 54 configurations matched the sequential field exactly
(max abs error 0.0), and every trial of a configuration ended with the same
checksum.

**Overall speed.** MPI barely helps on this machine. The best 2-process
results are a speedup of 1.01 at 2000² (both non-blocking variants, 10.6 s vs
10.7 s sequential). At 500² and 1000² the 2- and 4-process runs are at
best level with sequential (1.01 on `gradient` at 1000²) and mostly slower.
The 1-process MPI runs at 500² look faster than sequential (1.27), but the
sequential trials there were noisy (0.43 to 0.99 s). The NumPy stencil is limited by memory bandwidth, both cores
share that bandwidth, and halo exchange adds work on top.

**RQ1 (slab vs Cartesian).** On 2 processes `Compute_dims` gives a 2x1
grid, which is the same split as the slab version. So the 2-process
Cartesian/slab ratios (0.62 to 1.14, `full_rq1.csv`) measure run-to-run
noise and small code differences, not the decomposition. A real 2D split
(2x2) only appears at 4 processes, which is oversubscribed here, and there
Cartesian was slower in 5 of 6 cases (ratio 0.95 to 1.86). RQ1 can't be
answered properly without at least 4 physical cores. This is the main
limitation of the study.

**RQ2 (blocking vs non-blocking).** Non-blocking was faster in all 18
pairs: 17 to 64% faster on 2 processes and 40 to 68% on 4. At 500² and
1000² the time saved is 34 to 93% of the communication time measured in
the blocking run (one exception at 122%), so it fits the idea that overlap
hides part of the exchange. At 2000² on 2 processes the saving is *larger*
than the measured blocking comm time (1.20x for Cartesian, 1.42x for slab),
so blocking costs more than the time spent inside `Sendrecv`. A likely
reason is that blocking ranks wait on each other every step, and that cost
also shows up in cache and compute time outside the comm timer. This needs
explaining in the paper rather than claiming a clean match.

**Scenarios.** The stencil does the same work for any initial field, and
sequential times only vary from 2.03 to 2.46 s across the four scenarios.
The MPI runs vary more (e.g. `slab_blocking` takes 7.1 s on `uniform` vs
3.5 s on `gradient`), which is measurement noise on a shared laptop, not
a scenario effect.

**Outlier.** `slab_blocking` on 1 process at 2000² has a median of 62.8 s
(range 40.6 to 92.4 s), while the other 1-process variants took 11 to 14 s
with the same code path. Nothing about that configuration should be
slower, so this was most likely outside load or memory pressure on the 8 GB
machine during those trials. It is left in the raw data as measured.

| Figure | Shows |
|--------|-------|
| `fig_runtime` | median runtime (IQR bars) vs processes, per grid size |
| `fig_speedup` | speedup vs the sequential baseline |
| `fig_rq1_slab_vs_cartesian` | Cartesian / slab runtime ratio |
| `fig_rq2_overlap` | time saved by non-blocking vs blocking comm time |
| `fig_scenarios` | runtime by scenario at 1000², 2 processes |
| `fig_scenario_fields` | what each scenario looks like before and after diffusion |

## Data

All inputs are generated from a scenario name and a fixed seed. See `DATA.md`.
No external datasets, so there are no licences or preprocessing steps.

## Known limitations

- **One small machine.** 2 physical / 4 logical cores, so all communication
  is shared memory inside one node. The latency and overlap results don't
  carry over to a networked cluster.
- **4 processes are oversubscribed** (4 ranks on 2 physical cores). These
  runs are flagged in the raw data, shaded or hatched in the figures, and
  not used as scaling evidence. MPICH ranks busy-poll while they wait, so
  oversubscribed runs are much slower than the core count alone would
  suggest.
- **NumPy kernel.** The stencil is vectorised NumPy, which is memory-bandwidth
  bound and creates temporaries each step. Every variant uses the same
  kernel, so the comparison is fair, but absolute speeds are lower than a
  C version.
- **Comm time for non-blocking** is the time spent posting requests plus
  `Waitall`, so it measures waiting that the overlap didn't hide, not the
  total transfer time.
- Every rank builds the full initial field once during setup. That is
  simple and fine at 2000², but it wouldn't scale to very large grids.
- With Open MPI, oversubscribed runs need `--oversubscribe` (see
  `environment/tested_versions.md`).
- The scenarios are synthetic and say nothing about real Johannesburg
  temperatures.
