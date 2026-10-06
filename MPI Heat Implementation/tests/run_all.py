"""Runs every test_* function in tests/test_*.py. Works without pytest
(pytest tests/ also works if you have it).

  python tests/run_all.py
"""
import importlib
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    failed = 0
    total = 0
    for path in sorted(HERE.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            total += 1
            start = time.perf_counter()
            try:
                getattr(module, name)()
                status = "ok"
            except Exception:
                failed += 1
                status = "FAIL"
                traceback.print_exc()
            print(f"{status:4} {path.stem}.{name} ({time.perf_counter() - start:.1f}s)", flush=True)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
