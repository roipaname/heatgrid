"""Optimized sequential five-point stencil solver -- the reference baseline
that every MPI implementation's speedup is measured against (never the
one-process MPI run).

Two buffers, swapped by reference each step, one vectorized interior update
per timestep. Imports no MPI at all, so it runs with zero MPI overhead.
"""
import time

from heat import stencil_update
from scenarios import build_field


def run_sequential(rows, cols, scenario, seed, timesteps, r):
    """Returns (final_field, runtime_seconds). runtime_seconds times only
    the timestep loop, not field setup."""
    u_old = build_field(rows, cols, scenario, seed)
    u_new = u_old.copy()  # boundary values baked into both buffers up front

    start = time.perf_counter()
    for _ in range(timesteps):
        stencil_update(u_old, u_new, r)
        u_old, u_new = u_new, u_old
    runtime_seconds = time.perf_counter() - start

    return u_old, runtime_seconds
