"""Runs every configuration in a config file and records the raw trials.

  python scripts/run_experiments.py config/quick.json
  python scripts/run_experiments.py config/full.json

Each run writes a new results/raw/<name>_<timestamp>.csv (one row per trial)
and a matching .json with the config, software versions and git commit, so
old results are never overwritten. Configurations run in a shuffled but
seeded order so slow drift (thermal throttling etc) doesn't line up with
one variant. A failed configuration is logged and the rest still run.
"""
import argparse
import json
import platform
import random
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAT = ROOT / "src" / "heat.py"
RAW = ROOT / "results" / "raw"


def build_configs(cfg):
    seen = set()
    configs = []
    for sweep in cfg["sweeps"]:
        for rows, cols in sweep["grids"]:
            for scenario in sweep["scenarios"]:
                for variant in cfg["variants"]:
                    procs = [1] if variant == "sequential" else sweep["procs"]
                    for p in procs:
                        key = (variant, p, rows, cols, scenario)
                        if key not in seen:  # sweeps can overlap, run each point once
                            seen.add(key)
                            configs.append(key)
    random.Random(cfg["order_seed"]).shuffle(configs)
    return configs


def command(cfg, key, out, mpiexec, extra_args):
    variant, p, rows, cols, scenario = key
    cmd = [sys.executable, str(HEAT), "--variant", variant,
           "--rows", str(rows), "--cols", str(cols), "--scenario", scenario,
           "--steps", str(cfg["steps"]), "--r", str(cfg["r"]),
           "--trials", str(cfg["trials"]), "--warmup", str(cfg["warmup"]),
           "--out", str(out), "--quiet"]
    if variant != "sequential":
        cmd = [mpiexec, *cfg.get("mpiexec_args", []), *extra_args, "-n", str(p)] + cmd
    return cmd


def capture(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def environment_info(mpiexec):
    import numpy
    import mpi4py
    # ask a child process for the MPI version, importing mpi4py.MPI here
    # would start MPI in the driver and it spins while the benchmarks run
    mpi_lib = capture([sys.executable, "-c",
                       "from mpi4py import MPI; print(MPI.Get_library_version().splitlines()[0])"])
    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "mpi4py": mpi4py.__version__,
        "mpi_library": mpi_lib,
        "mpiexec": capture([mpiexec, "--version"]).splitlines()[:3],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": capture(["sysctl", "-n", "machdep.cpu.brand_string"]) if sys.platform == "darwin" else platform.processor(),
        "git_commit": capture(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
    }


def main():
    ap = argparse.ArgumentParser(description="Run an experiment config.")
    ap.add_argument("config", help="e.g. config/quick.json")
    ap.add_argument("--mpiexec", default="mpiexec")
    ap.add_argument("--mpiexec-args", default="", help='extra launcher flags, e.g. "--oversubscribe"')
    ap.add_argument("--timeout", type=float, default=1800, help="seconds per configuration")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    extra = shlex.split(args.mpiexec_args)
    configs = build_configs(cfg)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RAW / f"{cfg['name']}_{stamp}.csv"

    if args.dry_run:
        for key in configs:
            print(shlex.join(command(cfg, key, out, args.mpiexec, extra)))
        return 0

    RAW.mkdir(parents=True, exist_ok=True)
    meta = {"config_file": str(Path(args.config)), "config": cfg, "started": stamp,
            "environment": environment_info(args.mpiexec), "failed": []}
    print(f"{len(configs)} configurations -> {out.relative_to(ROOT)}")

    start = time.time()
    for i, key in enumerate(configs, 1):
        variant, p, rows, cols, scenario = key
        label = f"[{i}/{len(configs)}] {variant} p={p} {rows}x{cols} {scenario}"
        print(label, end=" ", flush=True)
        t0 = time.time()
        try:
            res = subprocess.run(command(cfg, key, out, args.mpiexec, extra),
                                 capture_output=True, text=True, timeout=args.timeout)
            ok = res.returncode == 0
            err = res.stderr.strip()[-500:]
        except subprocess.TimeoutExpired:
            ok, err = False, f"timed out after {args.timeout}s"
        if ok:
            print(f"ok ({time.time() - t0:.0f}s)")
        else:
            print("FAILED")
            print("   " + err.replace("\n", "\n   "))
            meta["failed"].append({"config": key, "error": err})

    meta["finished"] = datetime.now().strftime("%Y%m%d-%H%M%S")
    meta["wall_seconds"] = round(time.time() - start, 1)
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"done in {meta['wall_seconds']:.0f}s, {len(meta['failed'])} failed")
    return 1 if meta["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
