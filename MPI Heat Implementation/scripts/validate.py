"""Correctness check that prints the numbers behind the tests, for showing
and explaining correctness rather than just "ok".

  python scripts/validate.py              # MPI part on 2 and 4 processes
  python scripts/validate.py --procs 2

1. Sequential solver vs the exact decaying-sine solution
   u = sin(pi x) sin(pi y) exp(-2 pi^2 t) on three grids. The error should be
   small and drop by about 4 each time dx halves (FTCS is second order in
   space with r fixed).
2. Every MPI variant vs the sequential field, through the real CLI on an odd
   grid (uneven split). heat.py gathers the MPI field, compares it with the
   sequential one and exits 1 if they differ by more than 1e-12.

Takes a few seconds. Exits non-zero if anything fails.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from heatgrid.checks import analytic_field  # noqa: E402
from heatgrid.solvers.sequential import run_sequential  # noqa: E402

MPI_VARIANTS = ("slab_blocking", "slab_nonblocking", "cartesian_blocking", "cartesian_nonblocking")
T_END, R = 0.01, 0.2


def analytic(sizes=(41, 81, 161)):
    print(f"1. sequential vs exact solution, decaying_sine, t = {T_END}, r = {R}")
    print(f"   {'grid':>9} {'dx':>9} {'steps':>6} {'max abs err':>12} {'ratio':>6}")
    ok, prev = True, None
    for n in sizes:
        dx = 1.0 / (n - 1)
        steps = round(T_END / (R * dx * dx))
        field, _ = run_sequential(n, n, "decaying_sine", 0, steps, R)
        err = float(np.max(np.abs(field - analytic_field(n, n, steps, R))))
        ratio = prev / err if prev else None
        print(f"   {n:>4}x{n:<4} {dx:>9.5f} {steps:>6} {err:>12.3e} {ratio:>6.2f}" if ratio
              else f"   {n:>4}x{n:<4} {dx:>9.5f} {steps:>6} {err:>12.3e} {'':>6}")
        if ratio is not None and not 3.5 < ratio < 4.5:
            ok = False
        prev = err
    print("   -> error ~ dx^2 (ratio ~4 per halving): " + ("ok" if ok else "FAIL"))
    return ok


def mpi_vs_sequential(procs, rows=37, cols=53, steps=50):
    mpiexec = os.environ.get("MPIEXEC", "mpiexec")
    extra = shlex.split(os.environ.get("MPIEXEC_ARGS", ""))
    print(f"\n2. MPI vs sequential, {rows}x{cols} (odd, uneven split), single_hotspot, {steps} steps")
    print(f"   {'variant':<22} {'procs':>5} {'grid':>5} {'max abs err':>12}")
    ok = True
    for p in procs:
        for variant in MPI_VARIANTS:
            cmd = [mpiexec, *extra, "-n", str(p), sys.executable, str(ROOT / "src" / "heat.py"),
                   "--variant", variant, "--rows", str(rows), "--cols", str(cols),
                   "--steps", str(steps), "--trials", "1", "--warmup", "0"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            m = re.search(r"grid=(\S+).*max err (\S+)", res.stdout)
            if res.returncode == 0 and m:
                grid, err = m.group(1), m.group(2)
            else:
                ok = False
                grid, err = "-", "FAIL: " + (res.stderr.strip().splitlines() or ["?"])[-1]
            print(f"   {variant:<22} {p:>5} {grid:>5} {err:>12}")
    print("   -> every variant matches sequential to within 1e-12: " + ("ok" if ok else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="Print the correctness evidence.")
    ap.add_argument("--procs", type=int, nargs="+", default=[2, 4])
    args = ap.parse_args()
    ok = analytic()
    ok = mpi_vs_sequential(args.procs) and ok
    print("\nall checks passed" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
