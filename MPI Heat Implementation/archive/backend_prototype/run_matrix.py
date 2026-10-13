"""Runs a matrix of configurations by shelling out to run_config.py once per
configuration (`mpiexec -np P python run_config.py ...` for MPI
implementations, plain `python run_config.py ...` for sequential). Order is
randomised with a fixed seed to spread out thermal/frequency-scaling
effects; failed configurations are recorded (not silently skipped) and the
driver moves on.

Usage: python run_matrix.py smoke|scaling|scenario|full [--mpiexec PATH] [--python PATH]
"""
import argparse
import random
import subprocess
import sys
from pathlib import Path

IMPLEMENTATIONS = ("sequential", "slab_blocking", "slab_nonblocking",
                    "cartesian_blocking", "cartesian_nonblocking")
GRID_SIZES = ((500, 500), (1000, 1000), (2000, 2000))
PROCESS_COUNTS = (1, 2, 4)
SCENARIOS = ("uniform", "single_hotspot", "multiple_hotspots", "gradient")
SCALING_SCENARIO = "single_hotspot"
SCENARIO_GRID = (1000, 1000)
SCENARIO_PROCESSES = 2

FULL_TIMESTEPS = 200
SMOKE_TIMESTEPS = 20
SMOKE_GRID = (500, 500)
DIFFUSION_R = 0.20
TRIALS = 10
WARMUP = 1
ORDER_SEED = 7919

RUN_CONFIG = str(Path(__file__).parent / "run_config.py")


def scaling_configs(rows, cols, timesteps):
    configs = []
    for implementation in IMPLEMENTATIONS:
        procs = (1,) if implementation == "sequential" else PROCESS_COUNTS
        for p in procs:
            configs.append((implementation, rows, cols, SCALING_SCENARIO, timesteps, p))
    return configs


def scenario_configs():
    configs = []
    rows, cols = SCENARIO_GRID
    for scenario in SCENARIOS:
        if scenario == SCALING_SCENARIO:
            continue  # already covered by the scaling sweep at this grid/process point
        for implementation in IMPLEMENTATIONS:
            p = 1 if implementation == "sequential" else SCENARIO_PROCESSES
            configs.append((implementation, rows, cols, scenario, FULL_TIMESTEPS, p))
    return configs


def build_matrix(name):
    if name == "smoke":
        return scaling_configs(*SMOKE_GRID, SMOKE_TIMESTEPS)
    if name == "scaling":
        configs = []
        for rows, cols in GRID_SIZES:
            configs += scaling_configs(rows, cols, FULL_TIMESTEPS)
        return configs
    if name == "scenario":
        return scenario_configs()
    if name == "full":
        configs = []
        for rows, cols in GRID_SIZES:
            configs += scaling_configs(rows, cols, FULL_TIMESTEPS)
        configs += scenario_configs()
        return configs
    raise ValueError(f"unknown matrix '{name}'")


def build_command(config, mpiexec, python_exe):
    implementation, rows, cols, scenario, timesteps, processes = config
    args = [str(rows), str(cols), scenario, str(timesteps), str(DIFFUSION_R),
            "--trials", str(TRIALS), "--warmup", str(WARMUP), "--quiet"]
    if implementation == "sequential":
        return [python_exe, RUN_CONFIG, "sequential"] + args
    return [mpiexec, "-np", str(processes), python_exe, RUN_CONFIG, implementation] + args


def main():
    p = argparse.ArgumentParser()
    p.add_argument("matrix", choices=("smoke", "scaling", "scenario", "full"))
    p.add_argument("--mpiexec", default="mpiexec")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--timeout", type=float, default=1800.0)
    args = p.parse_args()

    configs = build_matrix(args.matrix)
    random.Random(ORDER_SEED).shuffle(configs)

    print(f"[run_matrix] {len(configs)} configurations (matrix={args.matrix}, order seed={ORDER_SEED})")
    n_ok, n_failed = 0, 0
    for i, config in enumerate(configs, start=1):
        implementation, rows, cols, scenario, timesteps, processes = config
        label = f"[{i}/{len(configs)}] {implementation} {rows}x{cols} p={processes} {scenario}"
        cmd = build_command(config, args.mpiexec, args.python)
        print(f"{label} ...", flush=True)
        try:
            result = subprocess.run(cmd, timeout=args.timeout, capture_output=True, text=True)
            if result.returncode == 0:
                n_ok += 1
            else:
                n_failed += 1
                print(f"  FAILED (exit {result.returncode})")
                print(result.stderr[-1500:], file=sys.stderr)
        except subprocess.TimeoutExpired:
            n_failed += 1
            print(f"  TIMEOUT after {args.timeout}s")

    print(f"[run_matrix] done: {n_ok} ok, {n_failed} failed")
    return 0 if n_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
