"""Five-point explicit FTCS stencil for the 2D heat equation, shared by the
sequential solver and all four MPI decompositions so they differ only in
decomposition/communication, never in arithmetic.

    u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4*u(i,j))

r = alpha * dt / dx^2 must stay <= 0.25 for stability (unit-square domain,
Dirichlet boundaries).
"""
import numpy as np

R_MAX = 0.25


def check_stability(r):
    if not (0.0 < r <= R_MAX):
        raise ValueError(f"r={r} must satisfy 0 < r <= {R_MAX}")


def stencil_update(u_old, u_new, r, row_lo=1, row_hi=None, col_lo=1, col_hi=None):
    """Writes the update for u_old[row_lo:row_hi, col_lo:col_hi] into u_new.
    Defaults to the full interior (everything but the outermost ring, which
    is a physical Dirichlet boundary or an MPI halo)."""
    row_hi = u_old.shape[0] - 1 if row_hi is None else row_hi
    col_hi = u_old.shape[1] - 1 if col_hi is None else col_hi

    c = u_old[row_lo:row_hi, col_lo:col_hi]
    n = u_old[row_lo - 1:row_hi - 1, col_lo:col_hi]
    s = u_old[row_lo + 1:row_hi + 1, col_lo:col_hi]
    w = u_old[row_lo:row_hi, col_lo - 1:col_hi - 1]
    e = u_old[row_lo:row_hi, col_lo + 1:col_hi + 1]

    u_new[row_lo:row_hi, col_lo:col_hi] = c + r * (n + s + w + e - 4.0 * c)
