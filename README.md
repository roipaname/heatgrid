# HeatGrid

Resource-aware MPI heat diffusion using domain decomposition for Johannesburg
urban heat scenarios (IT18X97 Parallel Programming).

Everything lives in **[`MPI Heat Implementation/`](MPI%20Heat%20Implementation/)**:
the Deliverable 2 implementation, experiments, results, figures, the
dashboard (`frontend/`) and its live-demo server. Start with its
[README](MPI%20Heat%20Implementation/README.md).

```bash
cd "MPI Heat Implementation"
conda env create -f environment/environment.yml && conda activate heatgrid
python tests/run_all.py
```

The first prototype (the old root `backend/` and `docs/`) is kept in
`MPI Heat Implementation/archive/` for history only.
