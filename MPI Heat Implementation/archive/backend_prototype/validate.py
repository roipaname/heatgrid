"""Correctness checks: cell-by-cell comparison against the sequential
reference, and an independent check against the closed-form decaying-sine
solution. Both operate on already-gathered full fields, never inside a
timed benchmark loop.
"""
import numpy as np

REL_EPSILON = 1e-12


def compare_fields(reference, candidate):
    """Cell-by-cell diff of two (rows, cols) fields. Returns
    (max_abs_err, mean_abs_err, max_rel_err)."""
    abs_diff = np.abs(candidate - reference)
    denom = np.maximum(np.abs(reference), REL_EPSILON)
    rel_diff = abs_diff / denom
    return float(np.max(abs_diff)), float(np.mean(abs_diff)), float(np.max(rel_diff))


def checksum(field):
    return float(np.sum(field)), float(np.sum(np.abs(field)))


def analytic_error(field, rows, cols, timesteps, r, alpha=1.0):
    """Compares a numerically-integrated decaying-sine field against the
    closed form u(x,y,t) = sin(pi x) sin(pi y) exp(-2 pi^2 alpha t), with
    dx = 1/(rows-1) and dt = r*dx^2/alpha (from r = alpha*dt/dx^2).
    Returns (l_inf_error, mean_abs_error, t_final)."""
    dx = 1.0 / (rows - 1)
    dt = r * dx * dx / alpha
    t_final = timesteps * dt

    y = np.linspace(0.0, 1.0, rows)[:, None]
    x = np.linspace(0.0, 1.0, cols)[None, :]
    analytic = np.sin(np.pi * x) * np.sin(np.pi * y) * np.exp(-2.0 * np.pi ** 2 * alpha * t_final)
    diff = np.abs(field - analytic)
    return float(np.max(diff)), float(np.mean(diff)), t_final
