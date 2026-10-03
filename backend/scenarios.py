"""Synthetic, seeded thermal scenarios over the unit square [0,1]x[0,1].

These are NOT measured Johannesburg temperatures -- they are qualitative
classes of thermal structure (uniform background, single hotspot, multiple
hotspots, gradient) used as reproducible initial conditions. Each scenario
is fully determined by (name, seed) via NumPy's Generator(PCG64), so the
same call always builds the same field.

Every rank builds the full global field (cheap at these grid sizes, a few
tens of MB) and then slices out its own local block -- simpler than
threading global/local index offsets through every caller.
"""
import numpy as np

SCENARIOS = ("uniform", "single_hotspot", "multiple_hotspots", "gradient")
ANALYTIC_SCENARIO = "decaying_sine"

SEEDS = {
    "uniform": 1001,
    "single_hotspot": 2001,
    "multiple_hotspots": 3001,
    "gradient": 4001,
    "decaying_sine": 5001,
}

BOUNDARY_VALUE = 0.3
BACKGROUND = 0.3


def build_field(rows, cols, scenario, seed):
    """Returns the full (rows, cols) global field for a scenario, with
    Dirichlet boundary values baked into the outermost ring."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0.0, 1.0, rows)[:, None]
    x = np.linspace(0.0, 1.0, cols)[None, :]
    X, Y = np.broadcast_arrays(x, y)

    if scenario == ANALYTIC_SCENARIO:
        field = np.sin(np.pi * X) * np.sin(np.pi * Y)
        boundary = 0.0
    elif scenario == "uniform":
        field = np.full((rows, cols), 0.5)
        boundary = BOUNDARY_VALUE
    elif scenario == "gradient":
        ax = rng.uniform(0.35, 0.45)
        ay = rng.uniform(0.15, 0.25)
        field = BACKGROUND + ax * X + ay * Y
        boundary = BOUNDARY_VALUE
    elif scenario in ("single_hotspot", "multiple_hotspots"):
        field = np.full((rows, cols), BACKGROUND)
        n_hotspots = 1 if scenario == "single_hotspot" else 4
        lo, hi = (0.35, 0.65) if n_hotspots == 1 else (0.15, 0.85)
        for _ in range(n_hotspots):
            hx = rng.uniform(lo, hi)
            hy = rng.uniform(lo, hi)
            amp = rng.uniform(0.3, 0.7)
            sigma = rng.uniform(0.05, 0.10)
            field = field + amp * np.exp(-((X - hx) ** 2 + (Y - hy) ** 2) / (2 * sigma ** 2))
        boundary = BOUNDARY_VALUE
    else:
        raise ValueError(f"unknown scenario '{scenario}'")

    field[0, :] = boundary
    field[-1, :] = boundary
    field[:, 0] = boundary
    field[:, -1] = boundary
    return field
