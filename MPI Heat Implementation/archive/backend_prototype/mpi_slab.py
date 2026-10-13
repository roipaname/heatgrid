"""1D horizontal slab decomposition: each rank owns a contiguous band of
global rows spanning the full width, plus a one-cell halo row above and
below. Rows are contiguous in memory, so no derived datatype is needed
here (unlike the Cartesian west/east columns in mpi_cartesian.py).
"""
import numpy as np
from mpi4py import MPI

from heat import stencil_update
from scenarios import build_field
from decomposition import block_distribute


def run_slab(comm, rows, cols, scenario, seed, timesteps, r, mode):
    """mode is 'blocking' or 'nonblocking'.
    Returns (u_old, row_start, local_rows, runtime_seconds, comm_seconds)."""
    rank, size = comm.Get_rank(), comm.Get_size()
    local_rows, row_start = block_distribute(rows, size, rank)
    up = rank - 1 if rank > 0 else MPI.PROC_NULL
    down = rank + 1 if rank < size - 1 else MPI.PROC_NULL
    is_top = row_start == 0
    is_bottom = row_start + local_rows == rows

    full = build_field(rows, cols, scenario, seed)  # deterministic, every rank
    u_old = np.zeros((local_rows + 2, cols))
    u_old[1:-1, :] = full[row_start:row_start + local_rows, :]
    u_new = u_old.copy()

    # Rows this rank is allowed to update: excludes the halo ring, and
    # excludes any owned row that is itself a fixed physical boundary.
    row_lo = 2 if is_top else 1
    row_hi = local_rows if is_bottom else local_rows + 1
    has_up, has_down = up != MPI.PROC_NULL, down != MPI.PROC_NULL
    strict_lo = row_lo + (1 if has_up else 0)
    strict_hi = row_hi - (1 if has_down else 0)

    comm_seconds = 0.0
    comm.Barrier()
    start = MPI.Wtime()

    if mode == "blocking":
        for _ in range(timesteps):
            t0 = MPI.Wtime()
            comm.Sendrecv(sendbuf=u_old[row_lo, :], dest=up, sendtag=1,
                           recvbuf=u_old[row_hi, :], source=down, recvtag=1)
            comm.Sendrecv(sendbuf=u_old[row_hi - 1, :], dest=down, sendtag=2,
                           recvbuf=u_old[row_lo - 1, :], source=up, recvtag=2)
            comm_seconds += MPI.Wtime() - t0

            stencil_update(u_old, u_new, r, row_lo=row_lo, row_hi=row_hi)
            u_old, u_new = u_new, u_old

    elif mode == "nonblocking":
        for _ in range(timesteps):
            t0 = MPI.Wtime()
            reqs = [
                comm.Irecv(u_old[row_lo - 1, :], source=up, tag=3),
                comm.Irecv(u_old[row_hi, :], source=down, tag=4),
                comm.Isend(np.ascontiguousarray(u_old[row_lo, :]), dest=up, tag=4),
                comm.Isend(np.ascontiguousarray(u_old[row_hi - 1, :]), dest=down, tag=3),
            ]
            comm_seconds += MPI.Wtime() - t0

            # Overlap window: strict interior depends only on already-owned data.
            stencil_update(u_old, u_new, r, row_lo=strict_lo, row_hi=strict_hi)

            t0 = MPI.Wtime()
            MPI.Request.Waitall(reqs)
            comm_seconds += MPI.Wtime() - t0

            if has_up:
                stencil_update(u_old, u_new, r, row_lo=row_lo, row_hi=row_lo + 1)
            if has_down:
                stencil_update(u_old, u_new, r, row_lo=row_hi - 1, row_hi=row_hi)

            u_old, u_new = u_new, u_old
    else:
        raise ValueError(f"unknown mode '{mode}'")

    runtime_seconds = MPI.Wtime() - start
    return u_old, row_start, local_rows, runtime_seconds, comm_seconds
