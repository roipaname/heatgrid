"""Turns a raw trial CSV into the tables used in the paper.

  python scripts/summarise.py                          # newest full_*.csv
  python scripts/summarise.py --name quick             # newest quick_*.csv
  python scripts/summarise.py results/raw/full_X.csv   # a specific file

Writes to results/processed/:
  <name>_summary.csv  median/IQR runtime, speedup, efficiency per configuration
  <name>_rq1.csv      slab vs Cartesian at each grid/process count
  <name>_rq2.csv      blocking vs non-blocking, with the measured comm time

Warm-up rows are dropped. Speedup is always against the sequential median for
the same grid, scenario and step count, never against the 1-rank MPI run.
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "processed"

KEY = ("variant", "nprocs", "rows", "cols", "scenario", "steps")


def newest(name):
    files = sorted(RAW.glob(f"{name}_*.csv"))
    if not files:
        sys.exit(f"no results/raw/{name}_*.csv yet, run scripts/run_experiments.py config/{name}.json first")
    return files[-1]


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("nprocs", "rows", "cols", "steps", "trial", "physical_cores"):
            r[k] = int(r[k])
        for k in ("runtime_s", "comm_s", "max_abs_err", "checksum", "r"):
            r[k] = float(r[k])
        r["warmup"] = r["warmup"] == "True"
        r["oversubscribed"] = r["oversubscribed"] == "True"
    return rows


def summarise(rows, source):
    groups = defaultdict(list)
    for r in rows:
        if not r["warmup"]:
            groups[tuple(r[k] for k in KEY)].append(r)

    out = []
    for key, trials in groups.items():
        t = np.array([r["runtime_s"] for r in trials])
        c = np.array([r["comm_s"] for r in trials])
        q1, med, q3 = np.percentile(t, [25, 50, 75])
        first = trials[0]
        out.append({
            **dict(zip(KEY, key)),
            "decomposition": first["decomposition"], "comm_mode": first["comm_mode"],
            "proc_grid": first["proc_grid"], "trials": len(trials),
            "median_s": med, "q1_s": q1, "q3_s": q3, "iqr_s": q3 - q1,
            "min_s": t.min(), "max_s": t.max(),
            "median_comm_s": float(np.median(c)),
            "comm_fraction": float(np.median(c)) / med,
            "max_abs_err": max(r["max_abs_err"] for r in trials),
            "checksums_match": len({r["checksum"] for r in trials}) == 1,
            "oversubscribed": first["oversubscribed"],
            "source": source,
        })

    seq = {(s["rows"], s["cols"], s["scenario"], s["steps"]): s["median_s"]
           for s in out if s["variant"] == "sequential"}
    for s in out:
        base = seq.get((s["rows"], s["cols"], s["scenario"], s["steps"]))
        s["speedup"] = base / s["median_s"] if base else None
        s["efficiency"] = s["speedup"] / s["nprocs"] if base else None

    out.sort(key=lambda s: (s["scenario"], s["rows"], s["variant"] != "sequential", s["variant"], s["nprocs"]))
    return out


def rq1(summary):
    # Cartesian / slab runtime ratio, < 1 means Cartesian was faster
    by = {(s["variant"], s["nprocs"], s["rows"], s["cols"], s["scenario"]): s for s in summary}
    table = []
    for s in summary:
        if s["decomposition"] != "slab" or s["nprocs"] < 2:
            continue
        cart = by.get((f"cartesian_{s['comm_mode']}", s["nprocs"], s["rows"], s["cols"], s["scenario"]))
        if cart:
            table.append({
                "rows": s["rows"], "cols": s["cols"], "scenario": s["scenario"],
                "nprocs": s["nprocs"], "comm_mode": s["comm_mode"], "cart_grid": cart["proc_grid"],
                "slab_median_s": s["median_s"], "cart_median_s": cart["median_s"],
                "cart_over_slab": cart["median_s"] / s["median_s"],
                "slab_comm_s": s["median_comm_s"], "cart_comm_s": cart["median_comm_s"],
                "oversubscribed": s["oversubscribed"],
            })
    return table


def rq2(summary):
    # saving from overlap, compared with how much comm there was to hide
    by = {(s["variant"], s["nprocs"], s["rows"], s["cols"], s["scenario"]): s for s in summary}
    table = []
    for s in summary:
        if s["comm_mode"] != "blocking" or s["nprocs"] < 2:
            continue
        nb = by.get((f"{s['decomposition']}_nonblocking", s["nprocs"], s["rows"], s["cols"], s["scenario"]))
        if nb:
            saving = s["median_s"] - nb["median_s"]
            table.append({
                "rows": s["rows"], "cols": s["cols"], "scenario": s["scenario"],
                "nprocs": s["nprocs"], "decomposition": s["decomposition"],
                "blocking_median_s": s["median_s"], "nonblocking_median_s": nb["median_s"],
                "saving_s": saving, "saving_pct": 100 * saving / s["median_s"],
                "blocking_comm_s": s["median_comm_s"], "nonblocking_comm_s": nb["median_comm_s"],
                # saving can't really exceed the comm time that was there to hide
                "saving_over_blocking_comm": saving / s["median_comm_s"] if s["median_comm_s"] else None,
                "oversubscribed": s["oversubscribed"],
            })
    return table


def write(path, rows):
    if not rows:
        print(f"  (nothing for {path.name})")
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: f"{v:.6g}" if isinstance(v, float) else v for k, v in r.items()})
    print(f"  {path.relative_to(ROOT)} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser(description="Summarise raw trial results.")
    ap.add_argument("raw", nargs="?", help="raw CSV, default is the newest for --name")
    ap.add_argument("--name", default="full")
    args = ap.parse_args()

    path = Path(args.raw) if args.raw else newest(args.name)
    name = path.stem.split("_")[0]
    rows = load(path)
    summary = summarise(rows, path.name)

    bad = [s for s in summary if s["max_abs_err"] > 1e-12 or not s["checksums_match"]]
    if bad:
        print(f"warning: {len(bad)} configurations failed a consistency check", file=sys.stderr)

    print(f"{path.name}: {len(rows)} raw rows, {len(summary)} configurations")
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / f"{name}_summary.csv", summary)
    write(OUT / f"{name}_rq1.csv", rq1(summary))
    write(OUT / f"{name}_rq2.csv", rq2(summary))


if __name__ == "__main__":
    main()
