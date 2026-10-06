"""1D slab decomposition. Each rank owns a band of full-width rows plus one
halo row above and below. Rows are contiguous so plain buffers are enough."""
import numpy as np
from mpi4py import MPI

from heatgrid.core.partition import block_range, check_split
from heatgrid.core.scenarios import build_field
from heatgrid.core.stencil import step


def check_slab(rows, cols, nprocs):
    check_split(rows, nprocs, "rows")


def run_slab(comm, rows, cols, scenario, seed, steps, r, mode):
    """Returns (owned_block, (row0, col0), elapsed, comm_time) for this rank."""
    rank, size = comm.Get_rank(), comm.Get_size()
    nrows, row0 = block_range(rows, size, rank)
    up = rank - 1 if rank > 0 else MPI.PROC_NULL
    down = rank + 1 if rank < size - 1 else MPI.PROC_NULL

    full = build_field(rows, cols, scenario, seed)
    u_old = np.zeros((nrows + 2, cols))
    u_old[1:-1, :] = full[row0:row0 + nrows, :]
    u_new = u_old.copy()
    del full

    # rows we update; skip the global top/bottom rows (fixed boundary)
    lo = 2 if row0 == 0 else 1
    hi = nrows if row0 + nrows == rows else nrows + 1
    has_up, has_down = up != MPI.PROC_NULL, down != MPI.PROC_NULL
    # inner rows that don't touch a halo, used for overlap
    in_lo = lo + has_up
    in_hi = hi - has_down

    comm_time = 0.0
    comm.Barrier()
    start = MPI.Wtime()

    if mode == "blocking":
        for _ in range(steps):
            t0 = MPI.Wtime()
            comm.Sendrecv(u_old[lo, :], dest=up, sendtag=1,
                          recvbuf=u_old[hi, :], source=down, recvtag=1)
            comm.Sendrecv(u_old[hi - 1, :], dest=down, sendtag=2,
                          recvbuf=u_old[lo - 1, :], source=up, recvtag=2)
            comm_time += MPI.Wtime() - t0

            step(u_old, u_new, r, lo, hi)
            u_old, u_new = u_new, u_old

    elif mode == "nonblocking":
        for _ in range(steps):
            t0 = MPI.Wtime()
            reqs = [
                comm.Irecv(u_old[lo - 1, :], source=up, tag=3),
                comm.Irecv(u_old[hi, :], source=down, tag=4),
                comm.Isend(u_old[lo, :], dest=up, tag=4),
                comm.Isend(u_old[hi - 1, :], dest=down, tag=3),
            ]
            comm_time += MPI.Wtime() - t0

            # interior first while halos are in flight
            step(u_old, u_new, r, in_lo, in_hi)

            t0 = MPI.Wtime()
            MPI.Request.Waitall(reqs)
            comm_time += MPI.Wtime() - t0

            if has_up:
                step(u_old, u_new, r, lo, lo + 1)
            if has_down:
                step(u_old, u_new, r, hi - 1, hi)
            u_old, u_new = u_new, u_old
    else:
        raise ValueError(f"unknown mode '{mode}'")

    elapsed = MPI.Wtime() - start
    return u_old[1:-1, :], (row0, 0), elapsed, comm_time
