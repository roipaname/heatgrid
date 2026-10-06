import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# override for Open MPI etc, e.g. MPIEXEC_ARGS="--oversubscribe"
MPIEXEC = os.environ.get("MPIEXEC", "mpiexec")
MPIEXEC_ARGS = shlex.split(os.environ.get("MPIEXEC_ARGS", ""))


def run_heat(args, nprocs=None):
    cmd = [sys.executable, str(SRC / "heat.py")] + [str(a) for a in args]
    if nprocs:
        cmd = [MPIEXEC, *MPIEXEC_ARGS, "-n", str(nprocs)] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
