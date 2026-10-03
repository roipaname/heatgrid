# HeatGrid

Resource-aware MPI heat diffusion using domain decomposition for Johannesburg urban heat scenarios.

## Research questions

- **RQ1**: under which grid sizes and process counts does 2D Cartesian decomposition
  outperform 1D slab decomposition at very low process counts (1–4, single shared-memory node)?
- **RQ2**: to what extent does non-blocking halo exchange with overlapped interior computation
  reduce runtime relative to blocking exchange, and is any reduction consistent with the
  communication time actually measured?

This is a computational study of decomposition/communication strategy, not a climate model. The
four synthetic scenarios (uniform, single hotspot, multiple hotspots, gradient) represent
qualitative classes of thermal structure reported for Johannesburg, not measured temperatures.

## Numerical model

Explicit forward-time centred-space (FTCS) five-point stencil for the 2D heat equation on the
unit square with Dirichlet boundaries:

```
u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4*u(i,j))
```

`r = alpha*dt/dx^2` is held at 0.20 (stability requires `r <= 0.25`).

## Implementations

| Name                     | Decomposition | Communication      |
|---------------------------|---------------|---------------------|
| `sequential`               | none (baseline)| n/a                |
| `slab_blocking`             | 1D slab        | `Sendrecv`         |
| `slab_nonblocking`          | 1D slab        | `Isend`/`Irecv` + overlap |
| `cartesian_blocking`        | 2D Cartesian   | `Sendrecv` (+ derived datatype for columns) |
| `cartesian_nonblocking`     | 2D Cartesian   | `Isend`/`Irecv` + overlap (+ derived datatype) |

The sequential implementation is the reference for speedup, never the 1-process MPI run (MPI
overhead should stay visible). All five implementations share the exact same stencil arithmetic
(`backend/heat.py`) so they differ only in decomposition and communication.

## Project layout

```
backend/            Python solver + MPI implementations + benchmark harness (flat, plain functions)
  heat.py              shared stencil kernel
  scenarios.py         seeded synthetic thermal fields
  sequential.py        baseline solver
  mpi_slab.py           1D slab, blocking + non-blocking
  mpi_cartesian.py      2D Cartesian, blocking + non-blocking, derived datatype
  validate.py            correctness comparison + analytic error
  validate_analytic.py   standalone decaying-sine analytic check
  run_config.py          runs ONE configuration, appends a CSV row
  run_matrix.py           runs a matrix of configurations
  export_json.py          CSV -> JSON for the frontend
frontend/            React (Vite) dashboard, reads exported JSON, no backend server needed
results/raw/          benchmark.csv (only real measured runs; never fabricated)
docs/                 methodology, reproducibility
```

## Quick start

```bash
uv sync
uv run python backend/run_matrix.py smoke        # small grid, few timesteps, all 5 implementations
uv run python backend/export_json.py               # CSV -> frontend/public/data/*.json

cd frontend
npm install
npm run dev                                          # opens the dashboard
```

See [docs/reproducibility.md](docs/reproducibility.md) for the full experiment matrix and exact
commands, and [docs/methodology.md](docs/methodology.md) for validation and benchmarking design.

## Limitations

Single machine (2 physical / 4 logical cores), all communication is intra-node shared memory, so
conclusions about latency/overlap are conditional on this platform class and do not transfer to
networked clusters. 4-process runs are intentionally oversubscribed (2 physical cores) and are
reported as a stress/functional data point, not scaling evidence. Scenarios are synthetic, not
calibrated against observations; no climate forecasting or policy claim is made.
