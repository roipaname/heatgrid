"""Sequential baseline. Same vectorised kernel as the MPI code and no MPI
import, so speedups are measured against a fair single-process version."""
import time

from heatgrid.core.scenarios import build_field
from heatgrid.core.stencil import step


def run_sequential(rows, cols, scenario, seed, steps, r):
    u_old = build_field(rows, cols, scenario, seed)
    u_new = u_old.copy()  # boundary values live in both buffers

    start = time.perf_counter()
    for _ in range(steps):
        step(u_old, u_new, r)
        u_old, u_new = u_new, u_old
    elapsed = time.perf_counter() - start

    return u_old, elapsed
