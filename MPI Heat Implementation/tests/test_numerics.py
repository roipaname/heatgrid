"""Sequential solver and helper checks (no MPI needed)."""
import numpy as np

import common  # noqa: F401  (puts src/ on the path)
from heatgrid.checks import analytic_field
from heatgrid.core.partition import block_range
from heatgrid.core.scenarios import SCENARIOS, build_field
from heatgrid.core.stencil import check_r, step
from heatgrid.solvers.sequential import run_sequential


def analytic_err(n, t_end=0.01, r=0.2):
    steps = round(t_end / (r / (n - 1) ** 2))
    field, _ = run_sequential(n, n, "decaying_sine", 0, steps, r)
    return np.max(np.abs(field - analytic_field(n, n, steps, r)))


def test_matches_analytic_solution():
    assert analytic_err(81) < 1e-4


def test_second_order_convergence():
    # halving dx should cut the error by about 4
    ratio = analytic_err(41) / analytic_err(81)
    assert 3.5 < ratio < 4.5, ratio


def test_constant_field_stays_constant():
    u = np.full((20, 30), 0.7)
    field = u.copy()
    for _ in range(50):
        step(u, field, 0.25)
        u, field = field, u
    assert np.allclose(u, 0.7, atol=1e-14)


def test_maximum_principle():
    # with r <= 0.25 the solution can't go above the initial max or below the min
    for name in SCENARIOS:
        start = build_field(64, 64, name, 1)
        end, _ = run_sequential(64, 64, name, 1, 300, 0.25)
        assert end.max() <= start.max() + 1e-12
        assert end.min() >= start.min() - 1e-12


def test_boundary_is_fixed():
    start = build_field(40, 50, "multiple_hotspots", 3001)
    end, _ = run_sequential(40, 50, "multiple_hotspots", 3001, 100, 0.2)
    for edge in (np.s_[0, :], np.s_[-1, :], np.s_[:, 0], np.s_[:, -1]):
        assert np.array_equal(start[edge], end[edge])


def test_scenarios_are_seeded():
    for name in SCENARIOS:
        assert np.array_equal(build_field(30, 30, name, 7), build_field(30, 30, name, 7))
    assert not np.array_equal(build_field(30, 30, "single_hotspot", 1),
                              build_field(30, 30, "single_hotspot", 2))


def test_block_range_covers_everything():
    for n in (10, 37, 100):
        for parts in (1, 2, 3, 4, 7):
            pieces = [block_range(n, parts, i) for i in range(parts)]
            assert sum(c for c, _ in pieces) == n
            for (c, s), (_, s_next) in zip(pieces, pieces[1:]):
                assert s + c == s_next


def test_unstable_r_rejected():
    for bad in (0.0, -0.1, 0.26, 1.0):
        try:
            check_r(bad)
        except ValueError:
            continue
        raise AssertionError(f"r={bad} was accepted")
