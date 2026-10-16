"""Local server for the dashboard's Live demo tab. It runs the real D2
programs (src/heat.py, scripts/validate.py) and returns the exact command,
its output and the exit code, so the browser shows a real execution, not
stored results.

  python scripts/demo_server.py            # http://localhost:8000
  python scripts/demo_server.py --port 8001

It serves the built dashboard (frontend/dist, from `npm run build`) on the
same port. In development, `npm run dev` proxies /api here instead.

It only listens on 127.0.0.1 and only accepts the options heat.py has,
checked against fixed lists and ranges. Nothing is passed through a shell.
Runs happen one at a time so they don't slow each other down.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from heatgrid import VARIANTS  # noqa: E402
from heatgrid.core.scenarios import ANALYTIC, DEFAULT_SEEDS, SCENARIOS  # noqa: E402
from heatgrid.records import physical_cores  # noqa: E402

DIST = ROOT / "frontend" / "dist"
MPIEXEC = os.environ.get("MPIEXEC", "mpiexec")
MPIEXEC_ARGS = shlex.split(os.environ.get("MPIEXEC_ARGS", ""))
MAX_PROCS = min(8, os.cpu_count() or 1)
LIMITS = {"rows": (3, 2000), "cols": (3, 2000), "steps": (1, 2000),
          "trials": (1, 10), "warmup": (0, 3), "procs": (1, MAX_PROCS)}
TIMEOUT = 300

_busy = threading.Lock()


class BadRequest(Exception):
    pass


def _int(body, key, default):
    try:
        value = int(body.get(key, default))
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must be a whole number")
    lo, hi = LIMITS[key]
    if not lo <= value <= hi:
        raise BadRequest(f"{key} must be between {lo} and {hi}")
    return value


def heat_command(body):
    variant = body.get("variant", "sequential")
    if variant not in VARIANTS:
        raise BadRequest(f"unknown variant {variant!r}")
    scenario = body.get("scenario", "single_hotspot")
    if scenario not in SCENARIOS + (ANALYTIC,):
        raise BadRequest(f"unknown scenario {scenario!r}")
    procs = 1 if variant == "sequential" else _int(body, "procs", 2)
    args = ["src/heat.py", "--variant", variant,
            "--rows", str(_int(body, "rows", 500)), "--cols", str(_int(body, "cols", 500)),
            "--scenario", scenario, "--steps", str(_int(body, "steps", 100)),
            "--trials", str(_int(body, "trials", 3)), "--warmup", str(_int(body, "warmup", 1))]
    launcher = [] if variant == "sequential" else [MPIEXEC, *MPIEXEC_ARGS, "-n", str(procs)]
    return launcher, args


def execute(launcher, args):
    """Runs `python <args>` (under mpiexec if given) from the project folder.
    Returns what the terminal would show: the command as typed, stdout, stderr."""
    shown = shlex.join([*([Path(launcher[0]).name, *launcher[1:]] if launcher else []), "python", *args])
    start = time.perf_counter()
    try:
        res = subprocess.run([*launcher, sys.executable, *args], cwd=ROOT,
                             capture_output=True, text=True, timeout=TIMEOUT)
        out, err, code = res.stdout, res.stderr, res.returncode
    except subprocess.TimeoutExpired:
        out, err, code = "", f"timed out after {TIMEOUT}s", -1
    return {"command": shown, "stdout": out, "stderr": err, "returncode": code,
            "wall_s": round(time.perf_counter() - start, 2)}


def parse_heat(stdout):
    m = re.search(r"^(\S+) (\d+)x(\d+) p=(\d+) grid=(\S+) (\S+): median (\S+)s over (\d+) trials, "
                  r"comm (\S+)%, max err (\S+)", stdout, re.M)
    if not m:
        return None
    trials = [float(t) for t in re.findall(r"trial \d+: (\S+)s", stdout)]
    trial_comm = [float(c) for c in re.findall(r"trial \d+: \S+s \(comm (\S+)s\)", stdout)]
    check = re.search(r"check vs sequential: max abs err (\S+)", stdout)
    return {"variant": m[1], "rows": int(m[2]), "cols": int(m[3]), "nprocs": int(m[4]),
            "proc_grid": m[5], "scenario": m[6], "median_s": float(m[7]), "trials": int(m[8]),
            "comm_pct": float(m[9]), "max_abs_err": float(m[10]), "trial_s": trials,
            "trial_comm_s": trial_comm,
            "checked_vs_sequential": bool(check)}


def parse_validate(stdout):
    analytic = [{"n": int(n), "dx": float(dx), "steps": int(s), "err": float(e),
                 "ratio": float(r) if r else None}
                for n, dx, s, e, r in re.findall(
                    r"^\s+(\d+)x\d+\s+(\S+)\s+(\d+)\s+(\S+e[-+]\d+)\s*(\S*)\s*$", stdout, re.M)]
    mpi = [{"variant": v, "nprocs": int(p), "proc_grid": g, "err": e}
           for v, p, g, e in re.findall(r"^\s+(\w+_\w+)\s+(\d+)\s+(\S+)\s+(\S+.*?)\s*$", stdout, re.M)
           if v in VARIANTS]
    return {"analytic": analytic, "mpi": mpi, "passed": "all checks passed" in stdout}


def info():
    return {"ok": True, "python": sys.version.split()[0], "mpiexec": shutil.which(MPIEXEC),
            "physical_cores": physical_cores(), "max_procs": MAX_PROCS,
            "variants": list(VARIANTS), "scenarios": list(SCENARIOS),
            "default_seeds": DEFAULT_SEEDS, "limits": LIMITS}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/"):
            sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")

    def _json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/info":
            return self._json(200, info())
        if self.path.startswith("/api/"):
            return self._json(404, {"error": "not found"})
        if not DIST.exists():
            return self._json(503, {"error": "frontend not built: run `npm run build` in frontend/, "
                                              "or use `npm run dev` for development"})
        if not (DIST / self.path.split("?")[0].lstrip("/")).exists():
            self.path = "/index.html"  # single-page app
        return super().do_GET()

    def do_POST(self):
        routes = {"/api/run": self.run_heat, "/api/validate": self.run_validate}
        handler = routes.get(self.path)
        if not handler:
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}") if length <= 10_000 else None
            if not isinstance(body, dict):
                raise BadRequest("expected a JSON object")
        except (ValueError, BadRequest) as e:
            return self._json(400, {"error": str(e) or "bad JSON"})
        if not _busy.acquire(blocking=False):
            return self._json(409, {"error": "another run is still going, wait for it to finish"})
        try:
            return self._json(200, handler(body))
        except BadRequest as e:
            return self._json(400, {"error": str(e)})
        finally:
            _busy.release()

    def run_heat(self, body):
        launcher, args = heat_command(body)
        result = execute(launcher, args)
        result["parsed"] = parse_heat(result["stdout"])
        return result

    def run_validate(self, body):
        procs = body.get("procs", [2, 4])
        if not (isinstance(procs, list) and procs and all(isinstance(p, int) for p in procs)
                and all(2 <= p <= MAX_PROCS for p in procs) and len(procs) <= 4):
            raise BadRequest(f"procs must be a list of 1-4 process counts between 2 and {MAX_PROCS}")
        result = execute([], ["scripts/validate.py", "--procs", *map(str, procs)])
        result["parsed"] = parse_validate(result["stdout"])
        return result


def main():
    ap = argparse.ArgumentParser(description="Live demo server for the dashboard.")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if not shutil.which(MPIEXEC):
        print(f"warning: {MPIEXEC} not found on PATH, MPI runs will fail "
              "(activate the heatgrid conda environment)", file=sys.stderr)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"HeatGrid demo server on http://localhost:{args.port}"
          + ("" if DIST.exists() else "  (API only: frontend/dist not built)"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
