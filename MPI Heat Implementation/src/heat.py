"""Run one configuration: correctness check, warm-up, then timed trials.

Examples:
  python src/heat.py --variant sequential --rows 500 --cols 500
  mpiexec -n 2 python src/heat.py --variant slab_nonblocking --rows 500 --cols 500 --out results/raw/test.csv

The correctness check runs first and is never timed. If an MPI result does
not match the sequential reference the program exits with status 1 and no
timings are recorded.
"""
import argparse
import os
import platform
import sys
from datetime import datetime

import numpy as np

from heatgrid import VARIANTS
from heatgrid.checks import TOLERANCE, assemble, max_abs_diff
from heatgrid.core.scenarios import ANALYTIC, DEFAULT_SEEDS, SCENARIOS
from heatgrid.core.stencil import check_r
from heatgrid.records import append_rows, physical_cores
from heatgrid.solvers.sequential import run_sequential


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="2D heat diffusion, sequential or MPI.")
    p.add_argument("--variant", choices=VARIANTS, default="sequential")
    p.add_argument("--rows", type=int, default=500)
    p.add_argument("--cols", type=int, default=500)
    p.add_argument("--scenario", choices=SCENARIOS + (ANALYTIC,), default="single_hotspot")
    p.add_argument("--seed", type=int, help="default: fixed seed for the scenario")
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--r", type=float, default=0.2, help="alpha*dt/dx^2, must be <= 0.25")
    p.add_argument("--trials", type=int, default=5)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--out", help="CSV file to append the trial rows to")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    if args.seed is None:
        args.seed = DEFAULT_SEEDS[args.scenario]
    return args


def bad_args(args):
    if args.rows < 3 or args.cols < 3:
        return "grid needs at least 3x3 points"
    if args.steps < 1:
        return "--steps must be at least 1"
    if args.trials < 1:
        return "--trials must be at least 1"
    if args.warmup < 0:
        return "--warmup can't be negative"
    try:
        check_r(args.r)
    except ValueError as e:
        return str(e)
    return None


def launcher_size():
    # lets the sequential version notice mpiexec -n N without importing mpi4py
    for key in ("PMI_SIZE", "OMPI_COMM_WORLD_SIZE", "MPI_LOCALNRANKS"):
        if key in os.environ:
            return int(os.environ[key])
    return 1


def median(values):
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def base_row(args, nprocs, grid):
    cores = physical_cores()
    decomp, _, mode = args.variant.partition("_")
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "host": platform.node(),
        "variant": args.variant,
        "decomposition": decomp,
        "comm_mode": mode or "none",
        "nprocs": nprocs,
        "proc_grid": grid,
        "rows": args.rows, "cols": args.cols,
        "scenario": args.scenario, "seed": args.seed,
        "steps": args.steps, "r": args.r,
        "physical_cores": cores,
        "oversubscribed": nprocs > cores,
    }


def report(args, rows):
    timed = [row for row in rows if not row["warmup"]]
    t = median([row["runtime_s"] for row in timed])
    c = median([row["comm_s"] for row in timed])
    first = rows[0]
    print(f"{args.variant} {args.rows}x{args.cols} p={first['nprocs']} grid={first['proc_grid']} "
          f"{args.scenario}: median {t:.4f}s over {len(timed)} trials, "
          f"comm {100 * c / t:.1f}%, max err {first['max_abs_err']:.1e}")
    if args.out:
        append_rows(args.out, rows)
        print(f"  {len(rows)} rows -> {args.out}")


def main_sequential(args):
    if launcher_size() > 1:
        sys.exit("error: the sequential variant must run on a single process")

    field, _ = run_sequential(args.rows, args.cols, args.scenario, args.seed, args.steps, args.r)
    if not np.isfinite(field).all():
        sys.exit("error: sequential result has NaN/inf values")

    base = base_row(args, 1, "1x1")
    rows = []
    for trial in range(args.warmup + args.trials):
        field, elapsed = run_sequential(args.rows, args.cols, args.scenario, args.seed, args.steps, args.r)
        rows.append({**base, "trial": trial - args.warmup + 1, "warmup": trial < args.warmup,
                     "runtime_s": elapsed, "comm_s": 0.0, "max_abs_err": 0.0,
                     "checksum": float(field.sum())})
        if not args.quiet and trial >= args.warmup:
            print(f"  trial {trial - args.warmup + 1}: {elapsed:.4f}s")
    report(args, rows)


def main_mpi(args):
    from mpi4py import MPI
    from heatgrid.solvers.cartesian import check_cartesian, process_grid, run_cartesian
    from heatgrid.solvers.slab import check_slab, run_slab

    comm = MPI.COMM_WORLD
    rank, size = comm.Get_rank(), comm.Get_size()
    decomp, mode = args.variant.split("_")

    if decomp == "slab":
        check, solver, grid = check_slab, run_slab, f"{size}x1"
    else:
        check, solver = check_cartesian, run_cartesian
        grid = "x".join(str(d) for d in process_grid(size))
    try:
        check(args.rows, args.cols, size)
    except ValueError as e:
        if rank == 0:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    def solve():
        return solver(comm, args.rows, args.cols, args.scenario, args.seed, args.steps, args.r, mode)

    # correctness first: gather the full field once and compare with sequential
    block, (row0, col0), _, _ = solve()
    parts = comm.gather((row0, col0, block.copy()), root=0)
    err = None
    if rank == 0:
        field = assemble(parts, args.rows, args.cols)
        ref, _ = run_sequential(args.rows, args.cols, args.scenario, args.seed, args.steps, args.r)
        err = max_abs_diff(field, ref) if np.isfinite(field).all() else float("inf")
    err = comm.bcast(err, root=0)
    if err > TOLERANCE:
        if rank == 0:
            print(f"error: {args.variant} disagrees with sequential, max abs err {err:.3e}", file=sys.stderr)
        sys.exit(1)
    if rank == 0 and not args.quiet:
        print(f"  check vs sequential: max abs err {err:.1e} (ok)")

    base = base_row(args, size, grid)
    rows = []
    for trial in range(args.warmup + args.trials):
        block, _, elapsed, comm_time = solve()
        # parallel runtime is the slowest rank
        elapsed = comm.reduce(elapsed, op=MPI.MAX, root=0)
        comm_time = comm.reduce(comm_time, op=MPI.MAX, root=0)
        total = comm.reduce(float(block.sum()), op=MPI.SUM, root=0)
        if rank == 0:
            rows.append({**base, "trial": trial - args.warmup + 1, "warmup": trial < args.warmup,
                         "runtime_s": elapsed, "comm_s": comm_time, "max_abs_err": err,
                         "checksum": total})
            if not args.quiet and trial >= args.warmup:
                print(f"  trial {trial - args.warmup + 1}: {elapsed:.4f}s (comm {comm_time:.4f}s)")
    if rank == 0:
        report(args, rows)


def main():
    args = parse_args()
    problem = bad_args(args)
    if problem:
        # every rank sees the same args, so only print once
        if os.environ.get("PMI_RANK", os.environ.get("OMPI_COMM_WORLD_RANK", "0")) == "0":
            print(f"error: {problem}", file=sys.stderr)
        sys.exit(2)
    if args.variant == "sequential":
        main_sequential(args)
    else:
        main_mpi(args)


if __name__ == "__main__":
    main()
