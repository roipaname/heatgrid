"""Exports processed results as JSON for the dashboard in frontend/.

  python scripts/export_frontend.py

Reads results/processed/<name>_summary.csv for every dataset listed below that
exists (run scripts/summarise.py first), and writes frontend/public/data/:

  datasets.json                 which datasets exist, and where they were measured
  <name>/results.json           one row per configuration (medians, speedup, ...)
  <name>/summary.json           headline numbers for the overview tiles
  scenario_previews.json        each scenario's initial field, and the field after diffusion

Nothing here re-runs a benchmark. The numbers are copied from the CSVs.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from heatgrid.core.scenarios import DEFAULT_SEEDS, SCENARIOS, build_field  # noqa: E402
from heatgrid.solvers.sequential import run_sequential  # noqa: E402

PROC = ROOT / "results" / "processed"
RAW = ROOT / "results" / "raw"
OUT = ROOT / "frontend" / "public" / "data"

DATASETS = [
    {"name": "full", "label": "Paper suite (i5, 2 cores)",
     "machine": "Intel Core i5-7360U, 2 physical / 4 logical cores, 8 GB RAM, macOS 13",
     "physical_cores": 2,
     "note": "The results behind the paper. 4 processes are oversubscribed on this machine."},
    {"name": "extended", "label": "Extended (Apple M1, 8 cores)",
     "machine": "Apple M1, 8 cores (4 performance + 4 efficiency), macOS",
     "physical_cores": 8,
     "note": "Extra runs for the dashboard on a different machine, up to 8 processes. "
             "The 8-process runs mix performance and efficiency cores. Not the paper results."},
    {"name": "quick", "label": "Quick demo config",
     "machine": "see the run metadata",
     "physical_cores": None,
     "note": "256x256, 100 steps. Checks that the pipeline works, not a performance result."},
]

INTS = ("nprocs", "rows", "cols", "steps", "trials")
FLOATS = ("median_s", "q1_s", "q3_s", "iqr_s", "min_s", "max_s", "median_comm_s",
          "comm_fraction", "max_abs_err", "speedup", "efficiency")


def load_summary(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        row = {k: r[k] for k in r}
        for k in INTS:
            row[k] = int(r[k])
        for k in FLOATS:
            row[k] = float(r[k]) if r.get(k) not in (None, "", "None") else None
        row["checksums_match"] = r["checksums_match"] == "True"
        row["oversubscribed"] = r["oversubscribed"] == "True"
        # field names the dashboard components use
        row["implementation"] = r["variant"]
        row["status"] = "ok"
        row["parallel_efficiency"] = row["efficiency"]
        row["median_comm_fraction"] = row["comm_fraction"]
        out.append(row)
    return out


def run_meta(source):
    meta = RAW / Path(source).with_suffix(".json").name
    if not meta.exists():
        return {}
    data = json.loads(meta.read_text())
    return {"environment": data.get("environment", {}), "wall_seconds": data.get("wall_seconds"),
            "started": data.get("started"), "failed": len(data.get("failed", []))}


def build_summary(rows, info):
    mpi = [r for r in rows if r["implementation"] != "sequential"]
    fair = [r for r in mpi if r["speedup"] is not None and not r["oversubscribed"] and r["nprocs"] > 1]
    best = max(fair, key=lambda r: r["speedup"]) if fair else None
    passed = [r for r in mpi if r["max_abs_err"] == 0.0 and r["checksums_match"]]
    return {
        "dataset": info["name"],
        "source": rows[0]["source"] if rows else None,
        "total_configurations": len(rows),
        "ok_configurations": len(rows),
        "failed_configurations": 0,
        "trials": rows[0]["trials"] if rows else None,
        "steps": rows[0]["steps"] if rows else None,
        "grid_sizes": [f"{n}x{n}" for n in sorted({r["rows"] for r in rows})],
        "process_counts": sorted({r["nprocs"] for r in rows}),
        "implementations": sorted({r["implementation"] for r in rows}),
        "scenarios": sorted({r["scenario"] for r in rows}),
        "correctness_checked": len(mpi),
        "correctness_passed": len(passed),
        "best_speedup": best,
        "oversubscribed_configurations": sum(r["oversubscribed"] for r in rows),
    }


def export_datasets():
    index = []
    for info in DATASETS:
        path = PROC / f"{info['name']}_summary.csv"
        if not path.exists():
            continue
        rows = load_summary(path)
        summary = build_summary(rows, info)
        summary["run"] = run_meta(summary["source"]) if summary["source"] else {}
        folder = OUT / info["name"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "results.json").write_text(json.dumps(rows, indent=1))
        (folder / "summary.json").write_text(json.dumps(summary, indent=1))
        index.append({**info, "source": summary["source"], "configurations": len(rows)})
        print(f"  {info['name']}: {len(rows)} configurations from {summary['source']}")
    (OUT / "datasets.json").write_text(json.dumps(index, indent=1))


def export_previews(size=60, steps=400, r=0.25):
    previews = {}
    for name in SCENARIOS:
        start = build_field(size, size, name, DEFAULT_SEEDS[name])
        end, _ = run_sequential(size, size, name, DEFAULT_SEEDS[name], steps, r)
        previews[name] = {
            "size": size, "min": float(start.min()), "max": float(start.max()),
            "values": [[round(v, 4) for v in row] for row in start.tolist()],
            "after_steps": steps,
            "after": [[round(v, 4) for v in row] for row in end.tolist()],
        }
    (OUT / "scenario_previews.json").write_text(json.dumps(previews))
    print(f"  scenario_previews.json ({len(previews)} scenarios)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"writing {OUT.relative_to(ROOT)}/")
    export_datasets()
    export_previews()


if __name__ == "__main__":
    main()
