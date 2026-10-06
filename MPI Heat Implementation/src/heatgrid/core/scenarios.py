"""Synthetic initial temperature fields on the unit square.

These are not real Johannesburg measurements, just reproducible shapes
(flat, one hotspot, several hotspots, a gradient). Random parameters come
from numpy's default_rng(seed) so a (scenario, seed) pair always gives the
same field. decaying_sine has a closed-form solution and is used for tests.
"""
import numpy as np

SCENARIOS = ("uniform", "single_hotspot", "multiple_hotspots", "gradient")
ANALYTIC = "decaying_sine"

DEFAULT_SEEDS = {
    "uniform": 1001,
    "single_hotspot": 2001,
    "multiple_hotspots": 3001,
    "gradient": 4001,
    "decaying_sine": 5001,
}

BOUNDARY = 0.3
BACKGROUND = 0.3


def build_field(rows, cols, scenario, seed):
    rng = np.random.default_rng(seed)
    y = np.linspace(0.0, 1.0, rows)[:, None]
    x = np.linspace(0.0, 1.0, cols)[None, :]
    X, Y = np.broadcast_arrays(x, y)

    if scenario == ANALYTIC:
        field = np.sin(np.pi * X) * np.sin(np.pi * Y)
        edge = 0.0
    elif scenario == "uniform":
        field = np.full((rows, cols), 0.5)
        edge = BOUNDARY
    elif scenario == "gradient":
        ax = rng.uniform(0.35, 0.45)
        ay = rng.uniform(0.15, 0.25)
        field = BACKGROUND + ax * X + ay * Y
        edge = BOUNDARY
    elif scenario in ("single_hotspot", "multiple_hotspots"):
        field = np.full((rows, cols), BACKGROUND)
        count = 1 if scenario == "single_hotspot" else 4
        lo, hi = (0.35, 0.65) if count == 1 else (0.15, 0.85)
        for _ in range(count):
            hx, hy = rng.uniform(lo, hi), rng.uniform(lo, hi)
            amp = rng.uniform(0.3, 0.7)
            sigma = rng.uniform(0.05, 0.10)
            field = field + amp * np.exp(-((X - hx) ** 2 + (Y - hy) ** 2) / (2 * sigma ** 2))
        edge = BOUNDARY
    else:
        raise ValueError(f"unknown scenario '{scenario}'")

    # Dirichlet boundary, never updated by the solvers
    field[0, :] = edge
    field[-1, :] = edge
    field[:, 0] = edge
    field[:, -1] = edge
    return field
