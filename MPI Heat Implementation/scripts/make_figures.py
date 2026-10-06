"""Builds every figure in paper/figures/ from results/processed/.

  python scripts/make_figures.py            # uses full_*.csv tables
  python scripts/make_figures.py --name quick

Run scripts/summarise.py first. Figures are PNG (300 dpi) and PDF. Only the
full suite goes to paper/figures/, anything else goes to
results/processed/figures_<name>/ so the paper figures aren't overwritten.
"""
import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from heatgrid.core.scenarios import DEFAULT_SEEDS, SCENARIOS, build_field  # noqa: E402
from heatgrid.solvers.sequential import run_sequential  # noqa: E402

PROC = ROOT / "results" / "processed"
FIGS = ROOT / "paper" / "figures"

MPI_VARIANTS = ["slab_blocking", "slab_nonblocking", "cartesian_blocking", "cartesian_nonblocking"]
COLORS = {"slab_blocking": "#2a78d6", "slab_nonblocking": "#eb6834",
          "cartesian_blocking": "#1baf7a", "cartesian_nonblocking": "#eda100",
          "sequential": "#52514e"}
MARKERS = {"slab_blocking": "o", "slab_nonblocking": "s",
           "cartesian_blocking": "^", "cartesian_nonblocking": "D"}
STYLES = {"blocking": "-", "nonblocking": "--"}
LABELS = {"slab_blocking": "Slab, blocking", "slab_nonblocking": "Slab, non-blocking",
          "cartesian_blocking": "Cartesian, blocking", "cartesian_nonblocking": "Cartesian, non-blocking",
          "sequential": "Sequential"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "lines.linewidth": 2, "legend.frameon": False,
    "savefig.bbox": "tight", "figure.dpi": 100,
})


def read(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if v in ("True", "False"):
                r[k] = v == "True"
            else:
                try:
                    r[k] = float(v) if "." in v or "e" in v else int(v)
                except ValueError:
                    pass
    return rows


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIGS / f"{name}.{ext}", dpi=300)
    plt.close(fig)
    print(f"  {(FIGS / name).relative_to(ROOT)}.png/.pdf")


def shade_oversubscribed(ax, procs, rows):
    over = sorted({r["nprocs"] for r in rows if r["oversubscribed"]})
    if over:
        ax.axvspan(over[0] / 1.3, max(procs) * 1.3, color=GRID, alpha=0.5, lw=0, zorder=0)
        ax.text(over[0], ax.get_ylim()[1], "oversubscribed", ha="center", va="top",
                fontsize=7, color=MUTED)


def scaling_rows(summary, scenario):
    return [r for r in summary if r["scenario"] == scenario]


def grids_of(rows):
    return sorted({(r["rows"], r["cols"]) for r in rows})


def fig_runtime_and_speedup(summary, scenario):
    rows = scaling_rows(summary, scenario)
    grids = grids_of(rows)
    procs = sorted({r["nprocs"] for r in rows if r["variant"] != "sequential"})

    for kind in ("runtime", "speedup"):
        fig, axes = plt.subplots(1, len(grids), figsize=(3.2 * len(grids), 3), squeeze=False)
        for ax, (nr, nc) in zip(axes[0], grids):
            here = [r for r in rows if (r["rows"], r["cols"]) == (nr, nc)]
            seq = [r for r in here if r["variant"] == "sequential"]
            for v in MPI_VARIANTS:
                pts = sorted((r for r in here if r["variant"] == v), key=lambda r: r["nprocs"])
                if not pts:
                    continue
                x = [r["nprocs"] for r in pts]
                if kind == "runtime":
                    y = [r["median_s"] for r in pts]
                    err = [[r["median_s"] - r["q1_s"] for r in pts], [r["q3_s"] - r["median_s"] for r in pts]]
                    ax.errorbar(x, y, yerr=err, color=COLORS[v], marker=MARKERS[v], ms=6,
                                ls=STYLES[v.split("_")[1]], capsize=2, label=LABELS[v])
                else:
                    ax.plot(x, [r["speedup"] for r in pts], color=COLORS[v], marker=MARKERS[v],
                            ms=6, ls=STYLES[v.split("_")[1]], label=LABELS[v])
            if kind == "runtime" and seq:
                ax.axhline(seq[0]["median_s"], color=COLORS["sequential"], lw=1.2, ls=":", label="Sequential")
                ax.set_yscale("log")
            if kind == "speedup":
                ax.plot(procs, procs, color=MUTED, lw=1, ls=":", label="Ideal")
                ax.axhline(1, color=GRID, lw=1)
            ax.set_xscale("log", base=2)
            ax.set_xticks(procs, [str(p) for p in procs])
            ax.minorticks_off()
            ax.set_title(f"{nr} x {nc}", fontsize=9, color=INK)
            ax.set_xlabel("MPI processes")
            shade_oversubscribed(ax, procs, here)
        axes[0][0].set_ylabel("Median runtime (s)" if kind == "runtime" else "Speedup vs sequential")
        handles, labels = axes[0][0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", ncol=len(labels), bbox_to_anchor=(0.5, -0.08))
        fig.tight_layout()
        save(fig, f"fig_{kind}")


def fig_rq1(table):
    if not table:
        return
    pts = [r for r in table if r["scenario"] == "single_hotspot"] or table
    labels = sorted({(r["rows"], r["nprocs"]) for r in pts})
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(6.5, 3))
    width = 0.38
    for i, mode in enumerate(("blocking", "nonblocking")):
        vals = []
        for g, p in labels:
            m = [r["cart_over_slab"] for r in pts if (r["rows"], r["nprocs"], r["comm_mode"]) == (g, p, mode)]
            vals.append(m[0] if m else np.nan)
        color = COLORS[f"cartesian_{mode}"]
        bars = ax.bar(x + (i - 0.5) * width, vals, width - 0.04, color=color, label=f"{mode}")
        for b, (g, p) in zip(bars, labels):
            if any(r["oversubscribed"] for r in pts if (r["rows"], r["nprocs"]) == (g, p)):
                b.set_hatch("///")
                b.set_edgecolor("white")
    ax.axhline(1, color=INK, lw=1)
    ax.set_xticks(x, [f"{g}²\np={p}" for g, p in labels])
    ax.set_ylabel("Cartesian / slab runtime")
    ax.set_title("RQ1: below 1 means Cartesian was faster (hatched = oversubscribed)", fontsize=9, color=INK)
    ax.legend(title="Halo exchange", loc="upper left")
    fig.tight_layout()
    save(fig, "fig_rq1_slab_vs_cartesian")


def fig_rq2(table):
    if not table:
        return
    pts = sorted((r for r in table if r["scenario"] == "single_hotspot"),
                 key=lambda r: (r["decomposition"], r["rows"], r["nprocs"])) or table
    x = np.arange(len(pts))
    fig, ax = plt.subplots(figsize=(9, 3.4))
    width = 0.38
    ax.bar(x - width / 2, [r["blocking_comm_s"] for r in pts], width - 0.04,
           color=COLORS["sequential"], label="Comm time in blocking run")
    ax.bar(x + width / 2, [r["saving_s"] for r in pts], width - 0.04,
           color=[COLORS[f"{r['decomposition']}_nonblocking"] for r in pts],
           label="Runtime saved by non-blocking")
    ax.axhline(0, color=INK, lw=1)
    ax.set_xticks(x, [f"{r['decomposition']}\n{r['rows']}²\np={r['nprocs']}" +
                      ("*" if r["oversubscribed"] else "") for r in pts], fontsize=7)
    ax.set_ylabel("Seconds")
    ax.set_title("RQ2: overlap saving vs. communication available to hide (* oversubscribed)",
                 fontsize=9, color=INK)
    ax.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.5))
    fig.tight_layout()
    save(fig, "fig_rq2_overlap")


def fig_scenarios(summary):
    # scenario sweep: the grid/process point that has every scenario
    counts = {}
    for r in summary:
        if r["variant"] != "sequential":
            counts.setdefault((r["rows"], r["nprocs"]), set()).add(r["scenario"])
    full = [k for k, s in counts.items() if len(s) == len(SCENARIOS)]
    if not full:
        return
    g, p = full[0]
    variants = ["sequential"] + MPI_VARIANTS
    fig, ax = plt.subplots(figsize=(6.5, 3))
    x = np.arange(len(SCENARIOS))
    width = 0.8 / len(variants)
    for i, v in enumerate(variants):
        want_p = 1 if v == "sequential" else p
        vals = []
        for s in SCENARIOS:
            m = [r["median_s"] for r in summary
                 if (r["variant"], r["rows"], r["nprocs"], r["scenario"]) == (v, g, want_p, s)]
            vals.append(m[0] if m else np.nan)
        ax.bar(x + (i - (len(variants) - 1) / 2) * width, vals, width - 0.02,
               color=COLORS[v], label=LABELS[v])
    ax.set_xticks(x, [s.replace("_", " ") for s in SCENARIOS])
    ax.set_ylabel("Median runtime (s)")
    ax.set_title(f"Runtime by scenario, {g} x {g}, MPI variants on {p} processes", fontsize=9, color=INK)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.42))
    fig.tight_layout()
    save(fig, "fig_scenarios")


def fig_fields(steps=2000, n=128):
    # initial and diffused fields, just to show what each scenario looks like
    fig, axes = plt.subplots(2, len(SCENARIOS), figsize=(2.2 * len(SCENARIOS), 4.4))
    for j, s in enumerate(SCENARIOS):
        start = build_field(n, n, s, DEFAULT_SEEDS[s])
        end, _ = run_sequential(n, n, s, DEFAULT_SEEDS[s], steps, 0.2)
        for i, f in enumerate((start, end)):
            im = axes[i][j].imshow(f, cmap="magma", vmin=0.3, vmax=1.0, origin="lower")
            axes[i][j].set_xticks([])
            axes[i][j].set_yticks([])
            axes[i][j].grid(False)
        axes[0][j].set_title(s.replace("_", " "), fontsize=9)
    axes[0][0].set_ylabel("initial")
    axes[1][0].set_ylabel(f"after {steps} steps")
    fig.colorbar(im, ax=axes, shrink=0.8, label="temperature (arb. units)")
    save(fig, "fig_scenario_fields")


def main():
    ap = argparse.ArgumentParser(description="Make the paper figures.")
    ap.add_argument("--name", default="full")
    args = ap.parse_args()

    summary_path = PROC / f"{args.name}_summary.csv"
    if not summary_path.exists():
        sys.exit(f"{summary_path.relative_to(ROOT)} not found, run scripts/summarise.py --name {args.name} first")
    global FIGS
    if args.name != "full":
        FIGS = PROC / f"figures_{args.name}"
    FIGS.mkdir(parents=True, exist_ok=True)
    summary = read(summary_path)
    print(f"figures from {summary_path.relative_to(ROOT)}")

    fig_runtime_and_speedup(summary, "single_hotspot")
    fig_rq1(read(PROC / f"{args.name}_rq1.csv") if (PROC / f"{args.name}_rq1.csv").exists() else [])
    fig_rq2(read(PROC / f"{args.name}_rq2.csv") if (PROC / f"{args.name}_rq2.csv").exists() else [])
    fig_scenarios(summary)
    fig_fields()


if __name__ == "__main__":
    main()
