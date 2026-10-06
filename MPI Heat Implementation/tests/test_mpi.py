"""Every MPI variant against the sequential reference, through the real CLI.

heat.py exits with status 1 if the gathered MPI field differs from the
sequential one, so a zero exit code plus an error of 0 in the CSV means
the check passed. Odd grid sizes make sure uneven splits work too.
"""
import csv
import tempfile
from pathlib import Path

from common import run_heat

MPI_VARIANTS = ("slab_blocking", "slab_nonblocking", "cartesian_blocking", "cartesian_nonblocking")
CASES = [
    # rows, cols, scenario
    (37, 53, "single_hotspot"),
    (64, 48, "multiple_hotspots"),
    (41, 41, "decaying_sine"),
]


def check_case(variant, nprocs, rows, cols, scenario):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "rows.csv"
        res = run_heat(["--variant", variant, "--rows", rows, "--cols", cols,
                        "--scenario", scenario, "--steps", 40, "--trials", 2,
                        "--warmup", 1, "--out", out, "--quiet"], nprocs=nprocs)
        label = f"{variant} p={nprocs} {rows}x{cols} {scenario}"
        assert res.returncode == 0, f"{label}\n{res.stderr}"
        with out.open() as f:
            rows_out = list(csv.DictReader(f))
    assert len(rows_out) == 3, label
    assert all(float(r["max_abs_err"]) == 0.0 for r in rows_out), label
    # every trial must end with the same field
    assert len({r["checksum"] for r in rows_out}) == 1, label
    assert all(int(r["nprocs"]) == nprocs for r in rows_out)


def test_mpi_matches_sequential():
    for variant in MPI_VARIANTS:
        for nprocs in (1, 2):
            for rows, cols, scenario in CASES:
                check_case(variant, nprocs, rows, cols, scenario)


def test_mpi_three_and_four_ranks():
    # 3 ranks gives an uneven 3x1 split, 4 gives a 2x2 Cartesian grid.
    # Only one case here since these are oversubscribed on small laptops.
    for variant in MPI_VARIANTS:
        for nprocs in (3, 4):
            check_case(variant, nprocs, *CASES[0])
