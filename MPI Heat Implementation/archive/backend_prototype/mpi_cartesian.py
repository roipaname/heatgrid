"""2D Cartesian decomposition: the grid is split into a p_row x p_col
process grid (from MPI_Dims_create / MPI_Cart_create, not hard-coded), each
rank owning a rectangular block plus a one-cell halo on all four sides.

Rows are contiguous, so north/south exchange uses plain buffers. Columns
are NOT contiguous (elements are `stride` doubles apart), so west/east
exchange uses a committed MPI derived datatype (MPI_Type_vector via
mpi4py's Create_vector), built once and freed at the end.
"""
import numpy as np
from mpi4py import MPI

from heat import stencil_update
from scenarios import build_field
from decomposition import block_distribute


def _column(buf, row_lo, col):
    """1-element view at buf[row_lo, col]; paired with a column datatype of
    count=(row range), this describes a strided column without copying."""
    flat = buf.reshape(-1)
    offset = row_lo * buf.shape[1] + col
    return flat[offset:offset + 1]


def run_cartesian(comm, rows, cols, scenario, seed, timesteps, r, mode):
    """mode is 'blocking' or 'nonblocking'.
    Returns (u_old, row_start, local_rows, col_start, local_cols,
    runtime_seconds, comm_seconds)."""
    size = comm.Get_size()
    dims = MPI.Compute_dims(size, [0, 0])  # MPI_Dims_create analogue
    cart = comm.Create_cart(dims, periods=[False, False], reorder=False)
    coords = cart.Get_coords(cart.Get_rank())
    p_row, p_col = dims

    local_rows, row_start = block_distribute(rows, p_row, coords[0])
    local_cols, col_start = block_distribute(cols, p_col, coords[1])
    north, south = cart.Shift(0, 1)
    west, east = cart.Shift(1, 1)

    is_top, is_bottom = row_start == 0, row_start + local_rows == rows
    is_left, is_right = col_start == 0, col_start + local_cols == cols

    full = build_field(rows, cols, scenario, seed)  # deterministic, every rank
    u_old = np.zeros((local_rows + 2, local_cols + 2))
    u_old[1:-1, 1:-1] = full[row_start:row_start + local_rows, col_start:col_start + local_cols]
    u_new = u_old.copy()

    row_lo, row_hi = (2 if is_top else 1), (local_rows if is_bottom else local_rows + 1)
    col_lo, col_hi = (2 if is_left else 1), (local_cols if is_right else local_cols + 1)

    has_n, has_s = north != MPI.PROC_NULL, south != MPI.PROC_NULL
    has_w, has_e = west != MPI.PROC_NULL, east != MPI.PROC_NULL
    strict_row_lo, strict_row_hi = row_lo + has_n, row_hi - has_s
    strict_col_lo, strict_col_hi = col_lo + has_w, col_hi - has_e

    # West/east halo columns span the owned row range [row_lo:row_hi); the
    # 5-point stencil never touches diagonal/corner halo cells, so north/
    # south and west/east exchanges never need to agree on corners.
    col_type = MPI.DOUBLE.Create_vector(row_hi - row_lo, 1, local_cols + 2)
    col_type.Commit()

    comm_seconds = 0.0
    cart.Barrier()
    start = MPI.Wtime()

    try:
        if mode == "blocking":
            for _ in range(timesteps):
                t0 = MPI.Wtime()
                cart.Sendrecv(sendbuf=u_old[row_lo, col_lo:col_hi], dest=north, sendtag=1,
                               recvbuf=u_old[row_hi, col_lo:col_hi], source=south, recvtag=1)
                cart.Sendrecv(sendbuf=u_old[row_hi - 1, col_lo:col_hi], dest=south, sendtag=2,
                               recvbuf=u_old[row_lo - 1, col_lo:col_hi], source=north, recvtag=2)
                cart.Sendrecv(sendbuf=[_column(u_old, row_lo, col_lo), 1, col_type], dest=west, sendtag=3,
                               recvbuf=[_column(u_old, row_lo, col_hi), 1, col_type], source=east, recvtag=3)
                cart.Sendrecv(sendbuf=[_column(u_old, row_lo, col_hi - 1), 1, col_type], dest=east, sendtag=4,
                               recvbuf=[_column(u_old, row_lo, col_lo - 1), 1, col_type], source=west, recvtag=4)
                comm_seconds += MPI.Wtime() - t0

                stencil_update(u_old, u_new, r, row_lo, row_hi, col_lo, col_hi)
                u_old, u_new = u_new, u_old

        elif mode == "nonblocking":
            for _ in range(timesteps):
                t0 = MPI.Wtime()
                reqs = [
                    cart.Irecv(u_old[row_lo - 1, col_lo:col_hi], source=north, tag=5),
                    cart.Irecv(u_old[row_hi, col_lo:col_hi], source=south, tag=6),
                    cart.Irecv([_column(u_old, row_lo, col_lo - 1), 1, col_type], source=west, tag=7),
                    cart.Irecv([_column(u_old, row_lo, col_hi), 1, col_type], source=east, tag=8),
                    cart.Isend(np.ascontiguousarray(u_old[row_lo, col_lo:col_hi]), dest=north, tag=6),
                    cart.Isend(np.ascontiguousarray(u_old[row_hi - 1, col_lo:col_hi]), dest=south, tag=5),
                    cart.Isend([_column(u_old, row_lo, col_lo), 1, col_type], dest=west, tag=8),
                    cart.Isend([_column(u_old, row_lo, col_hi - 1), 1, col_type], dest=east, tag=7),
                ]
                comm_seconds += MPI.Wtime() - t0

                stencil_update(u_old, u_new, r, strict_row_lo, strict_row_hi, strict_col_lo, strict_col_hi)

                t0 = MPI.Wtime()
                MPI.Request.Waitall(reqs)
                comm_seconds += MPI.Wtime() - t0

                if has_n:
                    stencil_update(u_old, u_new, r, row_lo, row_lo + 1, col_lo, col_hi)
                if has_s:
                    stencil_update(u_old, u_new, r, row_hi - 1, row_hi, col_lo, col_hi)
                if has_w:
                    stencil_update(u_old, u_new, r, row_lo, row_hi, col_lo, col_lo + 1)
                if has_e:
                    stencil_update(u_old, u_new, r, row_lo, row_hi, col_hi - 1, col_hi)

                u_old, u_new = u_new, u_old
        else:
            raise ValueError(f"unknown mode '{mode}'")
    finally:
        col_type.Free()

    runtime_seconds = MPI.Wtime() - start
    return u_old, row_start, local_rows, col_start, local_cols, runtime_seconds, comm_seconds
