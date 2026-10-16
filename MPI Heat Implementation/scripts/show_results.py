"""Prints the processed result tables in the terminal (made by summarise.py).

  python scripts/show_results.py               # full suite (the paper results)
  python scripts/show_results.py --name quick  # the quick demo config

Reads results/processed/<name>_summary.csv and <name>_rq2.csv only, so it
never re-runs anything. Medians of the measured (non-warm-up) trials.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "results" / "processed"


def read(path):
    if not path.exists():
        sys.exit(f"no {path.relative_to(ROOT)} yet, run scripts/summarise.py first")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def num(v, fmt):
    return format(float(v), fmt) if v not in ("", "None") else "-"


def main():
    ap = argparse.ArgumentParser(description="Show processed results.")
    ap.add_argument("--name", default="full")
    ap.add_argument("--scenario", default="single_hotspot")
    args = ap.parse_args()

    summary = [s for s in read(PROC / f"{args.name}_summary.csv") if s["scenario"] == args.scenario]
    source = summary[0]["source"] if summary else "?"
    print(f"{args.name} results ({source}), scenario {args.scenario}, "
          f"median of {summary[0]['trials'] if summary else '?'} trials\n")
    print(f"{'grid':>9} {'variant':<22} {'p':>2} {'pgrid':>5} {'median s':>9} {'IQR s':>7} "
          f"{'speedup':>7} {'comm %':>6} {'err':>7}")
    for s in sorted(summary, key=lambda s: (int(s["rows"]), s["variant"] != "sequential",
                                            s["variant"], int(s["nprocs"]))):
        flag = "  *" if s["oversubscribed"] == "True" else ""
        print(f"{s['rows'] + 'x' + s['cols']:>9} {s['variant']:<22} {s['nprocs']:>2} {s['proc_grid']:>5} "
              f"{num(s['median_s'], '.3f'):>9} {num(s['iqr_s'], '.3f'):>7} {num(s['speedup'], '.2f'):>7} "
              f"{100 * float(s['comm_fraction']):>6.1f} {num(s['max_abs_err'], '.0e'):>7}{flag}")
    if any(s["oversubscribed"] == "True" for s in summary):
        print("  * oversubscribed (more ranks than physical cores), not scaling evidence")

    rq2 = [r for r in read(PROC / f"{args.name}_rq2.csv") if r["scenario"] == args.scenario]
    if rq2:
        print("\nRQ2: non-blocking vs blocking (saving = blocking median - non-blocking median)\n")
        print(f"{'grid':>9} {'decomp':<9} {'p':>2} {'blocking s':>10} {'non-blk s':>9} "
              f"{'saving %':>8} {'saving / blk comm':>17}")
        for r in sorted(rq2, key=lambda r: (int(r["rows"]), int(r["nprocs"]), r["decomposition"])):
            flag = "  *" if r["oversubscribed"] == "True" else ""
            print(f"{r['rows'] + 'x' + r['cols']:>9} {r['decomposition']:<9} {r['nprocs']:>2} "
                  f"{num(r['blocking_median_s'], '.3f'):>10} {num(r['nonblocking_median_s'], '.3f'):>9} "
                  f"{num(r['saving_pct'], '.1f'):>8} {num(r['saving_over_blocking_comm'], '.2f'):>17}{flag}")


if __name__ == "__main__":
    main()
