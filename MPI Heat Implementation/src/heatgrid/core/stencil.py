"""Explicit FTCS five-point stencil for the 2D heat equation.

    u'(i,j) = u(i,j) + r * (u(i+1,j) + u(i-1,j) + u(i,j+1) + u(i,j-1) - 4u(i,j))

with r = alpha*dt/dx^2. Every solver calls step() so they only differ in
how the grid is split and how halos are exchanged.
"""

R_MAX = 0.25  # stability limit for the 2D explicit scheme


def check_r(r):
    if not 0.0 < r <= R_MAX:
        raise ValueError(f"r must be in (0, {R_MAX}], got {r}")


def step(u_old, u_new, r, row_lo=1, row_hi=None, col_lo=1, col_hi=None):
    # updates u_new[row_lo:row_hi, col_lo:col_hi], default is the whole interior
    if row_hi is None:
        row_hi = u_old.shape[0] - 1
    if col_hi is None:
        col_hi = u_old.shape[1] - 1

    c = u_old[row_lo:row_hi, col_lo:col_hi]
    n = u_old[row_lo - 1:row_hi - 1, col_lo:col_hi]
    s = u_old[row_lo + 1:row_hi + 1, col_lo:col_hi]
    w = u_old[row_lo:row_hi, col_lo - 1:col_hi - 1]
    e = u_old[row_lo:row_hi, col_lo + 1:col_hi + 1]
    u_new[row_lo:row_hi, col_lo:col_hi] = c + r * (n + s + w + e - 4.0 * c)
