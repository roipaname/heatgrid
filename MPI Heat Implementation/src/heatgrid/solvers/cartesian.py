"""2D Cartesian decomposition. MPI picks a px x py process grid
(Compute_dims + Create_cart) and each rank owns a block with a one cell
halo on every side.

North/south halos are contiguous rows. West/east halos are columns with a
stride, so they go through a committed vector datatype instead of being
copied into a temp buffer. The 5-point stencil never reads corner halo
cells so there is no diagonal exchange.
"""
import numpy as np
from mpi4py import MPI

from heatgrid.core.partition import block_range, check_split
from heatgrid.core.scenarios import build_field
from heatgrid.core.stencil import step


def process_grid(nprocs):
    return MPI.Compute_dims(nprocs, [0, 0])


def check_cartesian(rows, cols, nprocs):
    prow, pcol = process_grid(nprocs)
    check_split(rows, prow, "rows")
    check_split(cols, pcol, "cols")


def _col(buf, row, col):
    # 1-element view at buf[row, col], the vector type walks down from here
    i = row * buf.shape[1] + col
    return buf.reshape(-1)[i:i + 1]


def run_cartesian(comm, rows, cols, scenario, seed, steps, r, mode):
    """Returns (owned_block, (row0, col0), elapsed, comm_time) for this rank."""
    dims = process_grid(comm.Get_size())
    cart = comm.Create_cart(dims, periods=[False, False], reorder=False)
    prow, pcol = cart.Get_coords(cart.Get_rank())

    nrows, row0 = block_range(rows, dims[0], prow)
    ncols, col0 = block_range(cols, dims[1], pcol)
    north, south = cart.Shift(0, 1)
    west, east = cart.Shift(1, 1)

    full = build_field(rows, cols, scenario, seed)
    u_old = np.zeros((nrows + 2, ncols + 2))
    u_old[1:-1, 1:-1] = full[row0:row0 + nrows, col0:col0 + ncols]
    u_new = u_old.copy()
    del full

    # update range, global boundary rows/cols are skipped
    r_lo = 2 if row0 == 0 else 1
    r_hi = nrows if row0 + nrows == rows else nrows + 1
    c_lo = 2 if col0 == 0 else 1
    c_hi = ncols if col0 + ncols == cols else ncols + 1

    has_n, has_s = north != MPI.PROC_NULL, south != MPI.PROC_NULL
    has_w, has_e = west != MPI.PROC_NULL, east != MPI.PROC_NULL
    in_r_lo, in_r_hi = r_lo + has_n, r_hi - has_s
    in_c_lo, in_c_hi = c_lo + has_w, c_hi - has_e

    col_type = MPI.DOUBLE.Create_vector(r_hi - r_lo, 1, ncols + 2)
    col_type.Commit()

    comm_time = 0.0
    cart.Barrier()
    start = MPI.Wtime()

    try:
        if mode == "blocking":
            for _ in range(steps):
                t0 = MPI.Wtime()
                cart.Sendrecv(u_old[r_lo, c_lo:c_hi], dest=north, sendtag=1,
                              recvbuf=u_old[r_hi, c_lo:c_hi], source=south, recvtag=1)
                cart.Sendrecv(u_old[r_hi - 1, c_lo:c_hi], dest=south, sendtag=2,
                              recvbuf=u_old[r_lo - 1, c_lo:c_hi], source=north, recvtag=2)
                cart.Sendrecv([_col(u_old, r_lo, c_lo), 1, col_type], dest=west, sendtag=3,
                              recvbuf=[_col(u_old, r_lo, c_hi), 1, col_type], source=east, recvtag=3)
                cart.Sendrecv([_col(u_old, r_lo, c_hi - 1), 1, col_type], dest=east, sendtag=4,
                              recvbuf=[_col(u_old, r_lo, c_lo - 1), 1, col_type], source=west, recvtag=4)
                comm_time += MPI.Wtime() - t0

                step(u_old, u_new, r, r_lo, r_hi, c_lo, c_hi)
                u_old, u_new = u_new, u_old

        elif mode == "nonblocking":
            for _ in range(steps):
                t0 = MPI.Wtime()
                reqs = [
                    cart.Irecv(u_old[r_lo - 1, c_lo:c_hi], source=north, tag=5),
                    cart.Irecv(u_old[r_hi, c_lo:c_hi], source=south, tag=6),
                    cart.Irecv([_col(u_old, r_lo, c_lo - 1), 1, col_type], source=west, tag=7),
                    cart.Irecv([_col(u_old, r_lo, c_hi), 1, col_type], source=east, tag=8),
                    cart.Isend(u_old[r_lo, c_lo:c_hi], dest=north, tag=6),
                    cart.Isend(u_old[r_hi - 1, c_lo:c_hi], dest=south, tag=5),
                    cart.Isend([_col(u_old, r_lo, c_lo), 1, col_type], dest=west, tag=8),
                    cart.Isend([_col(u_old, r_lo, c_hi - 1), 1, col_type], dest=east, tag=7),
                ]
                comm_time += MPI.Wtime() - t0

                step(u_old, u_new, r, in_r_lo, in_r_hi, in_c_lo, in_c_hi)

                t0 = MPI.Wtime()
                MPI.Request.Waitall(reqs)
                comm_time += MPI.Wtime() - t0

                # edge strips that needed halo data
                if has_n:
                    step(u_old, u_new, r, r_lo, r_lo + 1, c_lo, c_hi)
                if has_s:
                    step(u_old, u_new, r, r_hi - 1, r_hi, c_lo, c_hi)
                if has_w:
                    step(u_old, u_new, r, r_lo, r_hi, c_lo, c_lo + 1)
                if has_e:
                    step(u_old, u_new, r, r_lo, r_hi, c_hi - 1, c_hi)
                u_old, u_new = u_new, u_old
        else:
            raise ValueError(f"unknown mode '{mode}'")
        elapsed = MPI.Wtime() - start
    finally:
        col_type.Free()
        cart.Free()

    return u_old[1:-1, 1:-1], (row0, col0), elapsed, comm_time
