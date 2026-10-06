# Tested versions

Everything in `results/` was produced on this setup. The exact versions for a
run are also saved next to the raw CSV (`results/raw/<name>_<stamp>.json`).

| Component | Version |
|-----------|---------|
| Machine   | MacBook Pro, Intel Core i5-7360U @ 2.30GHz, 2 physical / 4 logical cores, 8 GB RAM |
| OS        | macOS 13 (Darwin 22.6.0), x86_64 |
| Python    | 3.11.13 (conda-forge) |
| NumPy     | 2.4.6 |
| mpi4py    | 4.1.2 |
| MPI       | MPICH 4.3.2 (Hydra `mpiexec`) |
| matplotlib| 3.11.1 |

Open MPI should also work but is untested here. With Open MPI, running more
ranks than cores needs `--oversubscribe`, e.g.
`MPIEXEC_ARGS="--oversubscribe" python tests/run_all.py` and
`python scripts/run_experiments.py config/full.json --mpiexec-args="--oversubscribe"`.
