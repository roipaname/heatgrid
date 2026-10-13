"""Runs ONE configuration and appends one CSV row: warm-up (discarded) +
N timed trials, plus a one-time correctness check against the sequential
reference. Sequential mode never imports mpi4py; every other mode must be
launched with `mpiexec -np <processes> python run_config.py ...`.

Usage:
  python run_config.py sequential ROWS COLS SCENARIO TIMESTEPS R [--trials N] [--seed S] [--output CSV]
  mpiexec -np P python run_config.py slab_blocking ROWS COLS SCENARIO TIMESTEPS R ...
  (implementation is one of: sequential, slab_blocking, slab_nonblocking,
   cartesian_blocking, cartesian_nonblocking)
"""
import argparse
import csv
import platform
import subprocess
import sys
from pathlib import Path

from scenarios import SEEDS
from sequential import run_sequential
from validate import compare_fields, checksum

MAX_TRIALS = 10
RESULTS_CSV = Path(__file__).parent.parent / "results" / "raw" / "benchmark.csv"

FIELDNAMES = (
    ["implementation", "decomposition", "communication", "rows", "cols", "nprocs",
     "scenario", "seed", "timesteps", "diffusion_r"]
    + [f"run{i}_s" for i in range(1, MAX_TRIALS + 1)]
    + ["median_s", "iqr_s", "median_comm_s", "median_comm_fraction",
       "max_abs_err", "mean_abs_err", "max_rel_err",
       "checksum_sum", "checksum_abs_sum",
       "physical_cores", "oversubscribed", "status", "error_message"]
)


def median(values):
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def iqr(values):
    s = sorted(values)
    n = len(s)
    if n < 4:
        return 0.0
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    return q3 - q1


def physical_cores():
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.physicalcpu"],
                                  capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip())
    except (OSError, ValueError):
        pass
    return None


def append_row(row):
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not RESULTS_CSV.exists()
    with RESULTS_CSV.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "NA") for k in FIELDNAMES})


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("implementation", choices=(
        "sequential", "slab_blocking", "slab_nonblocking",
        "cartesian_blocking", "cartesian_nonblocking"))
    p.add_argument("rows", type=int)
    p.add_argument("cols", type=int)
    p.add_argument("scenario", choices=list(SEEDS.keys()))
    p.add_argument("timesteps", type=int)
    p.add_argument("r", type=float)
    p.add_argument("--trials", type=int, default=MAX_TRIALS)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--no-validate", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def run_seq_mode(args, seed, physcores):
    run_times = []
    field = None
    for trial in range(args.warmup + args.trials):
        field, t = run_sequential(args.rows, args.cols, args.scenario, seed, args.timesteps, args.r)
        if trial >= args.warmup:
            run_times.append(t)
            if not args.quiet:
                print(f"  trial {trial - args.warmup + 1}/{args.trials}: {t:.4f}s")

    row = {
        "implementation": "sequential", "decomposition": "sequential",
        "communication": "n/a", "rows": args.rows, "cols": args.cols, "nprocs": 1,
        "scenario": args.scenario, "seed": seed, "timesteps": args.timesteps,
        "diffusion_r": args.r,
        "median_s": median(run_times), "iqr_s": iqr(run_times),
        "median_comm_s": 0.0, "median_comm_fraction": 0.0,
        "max_abs_err": 0.0, "mean_abs_err": 0.0, "max_rel_err": 0.0,
        "physical_cores": physcores if physcores else "NA",
        "oversubscribed": False, "status": "ok", "error_message": "NA",
    }
    for i, t in enumerate(run_times[:MAX_TRIALS], start=1):
        row[f"run{i}_s"] = t
    row["checksum_sum"], row["checksum_abs_sum"] = checksum(field)
    return row


def owned_block(field, decomposition, local_rows, local_cols):
    """Slices out the owned (halo-excluded) region. Slab has no column
    halo (col_start=0, local_cols=cols always), Cartesian has a 1-cell
    halo on every side."""
    col_halo = 1 if decomposition == "cartesian" else 0
    return field[1:1 + local_rows, col_halo:col_halo + local_cols]


def gather_global_field(comm, local_field, row_start, local_rows, col_start, local_cols, rows, cols):
    """One-time pickle-based gather (not per-trial) reconstructing the full
    global field in correct row/col order from every rank's owned block."""
    import numpy as np
    packet = (row_start, col_start, local_rows, local_cols, local_field.copy())
    packets = comm.gather(packet, root=0)
    if packets is None:
        return None
    full = np.zeros((rows, cols))
    for rs, cs, nr, nc, block in packets:
        full[rs:rs + nr, cs:cs + nc] = block
    return full


def run_mpi_mode(args, seed, physcores):
    from mpi4py import MPI
    import mpi_slab
    import mpi_cartesian

    comm = MPI.COMM_WORLD
    rank, size = comm.Get_rank(), comm.Get_size()
    decomposition, communication = args.implementation.split("_", 1)
    run_fn = mpi_slab.run_slab if decomposition == "slab" else mpi_cartesian.run_cartesian

    correctness = {"max_abs_err": "NA", "mean_abs_err": "NA", "max_rel_err": "NA"}
    if not args.no_validate:
        result = run_fn(comm, args.rows, args.cols, args.scenario, seed, args.timesteps, args.r, communication)
        if decomposition == "slab":
            field, row_start, local_rows, _, _ = result
            col_start, local_cols = 0, args.cols
        else:
            field, row_start, local_rows, col_start, local_cols, _, _ = result
        owned = owned_block(field, decomposition, local_rows, local_cols)
        gathered = gather_global_field(comm, owned, row_start, local_rows, col_start, local_cols, args.rows, args.cols)
        comm.Barrier()
        if rank == 0:
            reference, _ = run_sequential(args.rows, args.cols, args.scenario, seed, args.timesteps, args.r)
            max_abs, mean_abs, max_rel = compare_fields(reference, gathered)
            correctness = {"max_abs_err": max_abs, "mean_abs_err": mean_abs, "max_rel_err": max_rel}
            if not args.quiet:
                print(f"  validate: max_abs_err={max_abs:.3e} max_rel_err={max_rel:.3e}")
        comm.Barrier()

    run_times, comm_times = [], []
    field = None
    owned_shape = None
    for trial in range(args.warmup + args.trials):
        result = run_fn(comm, args.rows, args.cols, args.scenario, seed, args.timesteps, args.r, communication)
        if decomposition == "slab":
            field, row_start, local_rows, t, ct = result
            col_start, local_cols = 0, args.cols
        else:
            field, row_start, local_rows, col_start, local_cols, t, ct = result
        max_t = comm.reduce(t, op=MPI.MAX, root=0)
        max_ct = comm.reduce(ct, op=MPI.MAX, root=0)
        if trial >= args.warmup and rank == 0:
            run_times.append(max_t)
            comm_times.append(max_ct)
            if not args.quiet:
                frac = max_ct / max_t if max_t else 0.0
                print(f"  trial {trial - args.warmup + 1}/{args.trials}: {max_t:.4f}s (comm {frac * 100:.1f}%)")
        owned_shape = (row_start, local_rows, col_start, local_cols)

    if rank != 0:
        return None

    owned = owned_block(field, decomposition, owned_shape[1], owned_shape[3])
    chk_sum, chk_abs = checksum(owned)  # rank 0's own block; full-field checksum needs a gather, done once above if validated
    row = {
        "implementation": args.implementation, "decomposition": decomposition,
        "communication": communication, "rows": args.rows, "cols": args.cols, "nprocs": size,
        "scenario": args.scenario, "seed": seed, "timesteps": args.timesteps, "diffusion_r": args.r,
        "median_s": median(run_times), "iqr_s": iqr(run_times),
        "median_comm_s": median(comm_times),
        "median_comm_fraction": (median(comm_times) / median(run_times)) if median(run_times) else 0.0,
        **correctness,
        "checksum_sum": chk_sum, "checksum_abs_sum": chk_abs,
        "physical_cores": physcores if physcores else "NA",
        "oversubscribed": bool(physcores and size > physcores),
        "status": "ok", "error_message": "NA",
    }
    for i, t in enumerate(run_times[:MAX_TRIALS], start=1):
        row[f"run{i}_s"] = t
    return row


def main():
    args = parse_args()
    seed = args.seed if args.seed is not None else SEEDS[args.scenario]
    physcores = physical_cores()

    base_row = {
        "implementation": args.implementation, "rows": args.rows, "cols": args.cols,
        "scenario": args.scenario, "seed": seed, "timesteps": args.timesteps, "diffusion_r": args.r,
    }
    try:
        if args.implementation == "sequential":
            row = run_seq_mode(args, seed, physcores)
        else:
            row = run_mpi_mode(args, seed, physcores)
        if row is not None:
            append_row(row)
    except Exception as exc:  # noqa: BLE001 -- record the failure, then re-raise
        failure = dict(base_row)
        failure.update({"status": "failed", "error_message": str(exc)})
        append_row(failure)
        raise


if __name__ == "__main__":
    main()
