# Reproducibility

## Target hardware

Intel Core i5-7360U, 2 physical / 4 logical cores, 8 GB RAM, macOS. No cluster or cloud access:
this is the deliberate resource constraint the study investigates.

## Software

- Python >= 3.11, managed with `uv` (`uv sync`; never `pip install` directly)
- `mpi4py` against a standard MPI implementation (MPICH or Open MPI). This was developed and
  tested against MPICH 4.3.2 via conda-forge (`conda install -c conda-forge openmpi` also works,
  though Open MPI additionally needs `mpirun --oversubscribe -np 4 ...` for oversubscribed runs;
  MPICH's Hydra launcher does not need or accept that flag).
  mpi4py >= 4 installs a prebuilt wheel that searches for `libmpi` at runtime; if MPI lives in a
  conda env it won't be found, so point mpi4py at it and put that env's `mpiexec` on `PATH`:
  `export MPI4PY_LIBMPI=$CONDA_PREFIX/lib/libmpi.12.dylib PATH=$CONDA_PREFIX/bin:$PATH`.
- Node.js + npm for the frontend (`frontend/`, Vite + React + Recharts)

## Build / environment

```bash
uv sync
cd frontend && npm install && cd ..
```

## Correctness validation

```bash
uv run python backend/validate_analytic.py 161 161 200 0.2
uv run mpiexec -np 2 uv run python backend/run_config.py slab_blocking 161 161 single_hotspot 200 0.2 --trials 1 --warmup 0
# repeat for slab_nonblocking, cartesian_blocking, cartesian_nonblocking
```

Each `run_config.py` invocation for an MPI implementation runs a one-time cell-by-cell comparison
against the sequential reference before timing trials and prints `max_abs_err`/`max_rel_err`.

## Smoke test (fast, small grid, a few minutes)

```bash
uv run python backend/run_matrix.py smoke
```

## Main scaling sweep (grid size x process count x implementation, scenario fixed at single_hotspot)

```bash
uv run python backend/run_matrix.py scaling
```

## Scenario comparison sweep (fixed grid/process count, all 4 scenarios)

```bash
uv run python backend/run_matrix.py scenario
```

## Full matrix (scaling + scenario comparison, the "run overnight" command)

```bash
uv run python backend/run_matrix.py full
```

All of the above append to `results/raw/benchmark.csv`. Failed configurations are recorded with
`status=failed` and an `error_message`, never silently skipped or converted into a fabricated
runtime.

## Exporting results to the dashboard

```bash
uv run python backend/export_json.py
cd frontend && npm run dev
```

If `results/raw/benchmark.csv` doesn't exist yet, `export_json.py` writes an empty `results.json`
and the dashboard shows "no measured results available" rather than placeholder numbers.

## Random seeds

Scenario seeds are fixed: `uniform=1001, single_hotspot=2001, multiple_hotspots=3001,
gradient=4001, decaying_sine=5001` (`backend/scenarios.py::SEEDS`). Experiment run order is
randomised with a fixed seed (`ORDER_SEED=7919` in `backend/run_matrix.py`) to spread out
thermal/frequency-scaling effects while staying reproducible.

## Git commit

Record the commit the results were generated from: `git rev-parse HEAD`.
