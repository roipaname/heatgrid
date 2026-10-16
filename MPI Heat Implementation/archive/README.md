# Archive: early prototype (not the D2 implementation)

Everything in this folder is the first version of HeatGrid. It is kept for
history only and nothing in the main folder uses it.

- `backend_prototype/` was the original flat Python solver and benchmark
  harness (`run_matrix.py`, `run_config.py`, `export_json.py`), with its own
  `pyproject.toml`. It is replaced by `src/` and `scripts/` in the main folder.
- `backend_prototype_results/` holds a 20-step smoke run of that prototype,
  recorded on an Apple M1 on 2026-10-12.
- `docs/` contains the prototype's methodology and reproducibility notes, plus
  `research_summary.md`. That summary describes an incomplete prototype run
  (10 trials, 30 of 39 scaling configurations), and its numbers differ from
  the D2 results. **Don't cite them.** Use `results/` in the main folder instead.
- `data/` is the original logo asset. The same file is in `frontend/public/logo.png`.
