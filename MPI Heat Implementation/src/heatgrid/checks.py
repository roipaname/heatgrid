"""Correctness helpers. Nothing here runs inside a timed region."""
import numpy as np

# Every version does the exact same arithmetic per cell, so MPI results
# should match the sequential field bit for bit. Small slack just in case.
TOLERANCE = 1e-12


def max_abs_diff(a, b):
    return float(np.max(np.abs(a - b)))


def assemble(parts, rows, cols):
    # parts is a list of (row0, col0, block) from comm.gather
    field = np.full((rows, cols), np.nan)
    for row0, col0, block in parts:
        field[row0:row0 + block.shape[0], col0:col0 + block.shape[1]] = block
    return field


def analytic_field(rows, cols, steps, r, alpha=1.0):
    # u = sin(pi x) sin(pi y) exp(-2 pi^2 alpha t), dx = 1/(rows-1)
    dx = 1.0 / (rows - 1)
    t = steps * r * dx * dx / alpha
    y = np.linspace(0.0, 1.0, rows)[:, None]
    x = np.linspace(0.0, 1.0, cols)[None, :]
    return np.sin(np.pi * x) * np.sin(np.pi * y) * np.exp(-2.0 * np.pi ** 2 * alpha * t)
