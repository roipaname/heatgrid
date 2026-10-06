#!/usr/bin/env bash
# Quick check that everything works: tests, a small sequential and MPI run,
# then the quick experiment config with its summary and figures.
# Usage: bash scripts/quick_demo.sh
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}

echo "== correctness tests"
$PY tests/run_all.py

echo; echo "== sequential vs MPI, 256x256"
$PY src/heat.py --variant sequential --rows 256 --cols 256 --steps 100
mpiexec ${MPIEXEC_ARGS} -n 2 $PY src/heat.py --variant cartesian_nonblocking --rows 256 --cols 256 --steps 100

echo; echo "== quick experiment config"
$PY scripts/run_experiments.py config/quick.json
$PY scripts/summarise.py --name quick
$PY scripts/make_figures.py --name quick
