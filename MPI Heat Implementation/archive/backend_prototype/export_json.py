"""Converts results/raw/benchmark.csv into JSON the React frontend can
fetch directly (frontend/public/data/*.json) -- no live backend server.
Also exports small preview grids of each synthetic scenario's initial
field, computed directly (no benchmark run needed).

Never fabricates data: if benchmark.csv doesn't exist yet, results.json is
written as an empty list and the frontend shows a "run the benchmark
suite" message instead of fake numbers.

Usage: python export_json.py
"""
import csv
import json
from pathlib import Path

from scenarios import SCENARIOS, SEEDS, build_field

ROOT = Path(__file__).parent.parent
RAW_CSV = ROOT / "results" / "raw" / "benchmark.csv"
OUT_DIR = ROOT / "frontend" / "public" / "data"

NUMERIC_FIELDS = (
    "rows", "cols", "nprocs", "seed", "timesteps", "diffusion_r",
    "median_s", "iqr_s", "median_comm_s", "median_comm_fraction",
    "max_abs_err", "mean_abs_err", "max_rel_err",
    "checksum_sum", "checksum_abs_sum", "physical_cores",
)


def _coerce(row):
    out = dict(row)
    for key in NUMERIC_FIELDS:
        val = out.get(key)
        if val in (None, "", "NA"):
            out[key] = None
        else:
            try:
                out[key] = float(val)
            except ValueError:
                pass
    out["oversubscribed"] = str(row.get("oversubscribed")).lower() == "true"
    return out


def load_rows():
    if not RAW_CSV.exists():
        return []
    with open(RAW_CSV, newline="") as f:
        return [_coerce(r) for r in csv.DictReader(f)]


def with_speedup(rows):
    """Adds speedup/efficiency by matching each row to the sequential
    baseline row with the same (rows, cols, scenario, timesteps)."""
    baselines = {
        (r["rows"], r["cols"], r["scenario"], r["timesteps"]): r["median_s"]
        for r in rows
        if r["implementation"] == "sequential" and r["status"] == "ok"
    }
    out = []
    for r in rows:
        key = (r["rows"], r["cols"], r["scenario"], r["timesteps"])
        seq_time = baselines.get(key)
        speedup = (seq_time / r["median_s"]) if seq_time and r.get("median_s") else None
        r = dict(r)
        r["speedup"] = speedup
        r["parallel_efficiency"] = (speedup / r["nprocs"]) if speedup and r.get("nprocs") else None
        out.append(r)
    return out


def build_summary(rows):
    """Aggregate KPIs for the dashboard overview -- computed once here in
    plain Python rather than recomputed ad hoc in the frontend."""
    ok = [r for r in rows if r["status"] == "ok"]
    mpi_rows = [r for r in ok if r["implementation"] != "sequential"]
    failed = [r for r in rows if r["status"] == "failed"]

    best = None
    for r in mpi_rows:
        if r.get("speedup") is not None and (best is None or r["speedup"] > best["speedup"]):
            best = r

    correctness_rows = [r for r in mpi_rows if r.get("max_abs_err") is not None]
    passed = [r for r in correctness_rows
              if r["max_abs_err"] <= 1e-8 or (r.get("max_rel_err") or 1) <= 1e-6]

    return {
        "total_configurations": len(rows),
        "ok_configurations": len(ok),
        "failed_configurations": len(failed),
        "grid_sizes": sorted({f"{int(r['rows'])}x{int(r['cols'])}" for r in ok}, key=len),
        "process_counts": sorted({int(r["nprocs"]) for r in ok if r["nprocs"] is not None}),
        "implementations": sorted({r["implementation"] for r in ok}),
        "scenarios": sorted({r["scenario"] for r in ok}),
        "correctness_checked": len(correctness_rows),
        "correctness_passed": len(passed),
        "best_speedup": best,
    }


def export_results():
    rows = with_speedup(load_rows())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(rows, indent=2))
    (OUT_DIR / "summary.json").write_text(json.dumps(build_summary(rows), indent=2))
    print(f"wrote {len(rows)} rows -> {OUT_DIR / 'results.json'}")
    print(f"wrote summary -> {OUT_DIR / 'summary.json'}")


def export_scenario_previews(size=60):
    previews = {}
    for scenario in SCENARIOS:
        field = build_field(size, size, scenario, SEEDS[scenario])
        previews[scenario] = {
            "size": size,
            "min": float(field.min()),
            "max": float(field.max()),
            "values": [[round(v, 4) for v in row] for row in field.tolist()],
        }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "scenario_previews.json").write_text(json.dumps(previews))
    print(f"wrote {len(previews)} scenario previews -> {OUT_DIR / 'scenario_previews.json'}")


if __name__ == "__main__":
    export_results()
    export_scenario_previews()
