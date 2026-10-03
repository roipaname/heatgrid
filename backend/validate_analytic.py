"""Analytic validation: runs the sequential solver on the decaying-sine
initial condition and compares the result against the closed-form solution.
Independent of the cross-implementation agreement check in run_config.py --
this measures true numerical error, not just implementation agreement.

Usage: python validate_analytic.py [ROWS] [COLS] [TIMESTEPS] [R]
"""
import sys

from scenarios import SEEDS, ANALYTIC_SCENARIO
from sequential import run_sequential
from validate import analytic_error

L_INF_TOLERANCE = 0.05  # generous bound for an O(dt)+O(dx^2) FTCS scheme


def main():
    rows = int(sys.argv[1]) if len(sys.argv) > 1 else 161
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 161
    timesteps = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    r = float(sys.argv[4]) if len(sys.argv) > 4 else 0.20

    field, runtime = run_sequential(rows, cols, ANALYTIC_SCENARIO, SEEDS[ANALYTIC_SCENARIO], timesteps, r)
    l_inf, mean_abs, t_final = analytic_error(field, rows, cols, timesteps, r)

    passed = l_inf < L_INF_TOLERANCE
    print(f"grid={rows}x{cols} timesteps={timesteps} r={r} t_final={t_final:.5f}")
    print(f"L_inf={l_inf:.3e}  mean_abs={mean_abs:.3e}  -> {'PASS' if passed else 'FAIL'} "
          f"(tolerance {L_INF_TOLERANCE:.3e})")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
