"""Raw result rows. One row per trial (warm-up included and flagged)."""
import csv
import os
import platform
import subprocess
from pathlib import Path

FIELDS = [
    "timestamp", "host", "variant", "decomposition", "comm_mode",
    "nprocs", "proc_grid", "rows", "cols", "scenario", "seed", "steps", "r",
    "trial", "warmup", "runtime_s", "comm_s", "max_abs_err", "checksum",
    "physical_cores", "oversubscribed",
]


def physical_cores():
    try:
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.physicalcpu"],
                                 capture_output=True, text=True, timeout=5)
            return int(out.stdout)
        if platform.system() == "Linux":
            cores = set()
            phys = None
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("physical id"):
                        phys = line.split(":")[1].strip()
                    elif line.startswith("core id"):
                        cores.add((phys, line.split(":")[1].strip()))
            if cores:
                return len(cores)
    except (OSError, ValueError):
        pass
    return os.cpu_count() or 1


def append_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
