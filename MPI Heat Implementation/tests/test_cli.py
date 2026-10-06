"""Bad parameters must fail with a clear message and a non-zero exit."""
from common import run_heat

BAD_ARGS = [
    (["--r", "0.3"], "r must be"),
    (["--r", "0"], "r must be"),
    (["--cols", "2"], "at least 3x3"),
    (["--steps", "0"], "--steps"),
    (["--trials", "0"], "--trials"),
    (["--warmup", "-1"], "--warmup"),
    (["--scenario", "nope"], "invalid choice"),
    (["--variant", "nope"], "invalid choice"),
]


def test_bad_arguments_fail():
    for args, message in BAD_ARGS:
        res = run_heat(["--rows", "20", "--cols", "20"] + args)
        assert res.returncode != 0, args
        assert message in res.stderr, (args, res.stderr)


def test_too_many_ranks_for_grid():
    res = run_heat(["--variant", "slab_blocking", "--rows", "8", "--cols", "8"], nprocs=4)
    assert res.returncode == 2
    assert "per rank" in res.stderr
    assert res.stderr.count("error:") == 1  # printed by rank 0 only


def test_sequential_refuses_multiple_ranks():
    res = run_heat(["--variant", "sequential", "--rows", "20", "--cols", "20"], nprocs=2)
    assert res.returncode != 0
    assert "single process" in res.stderr


def test_quick_run_works():
    res = run_heat(["--rows", "30", "--cols", "30", "--steps", "5", "--trials", "1", "--warmup", "0"])
    assert res.returncode == 0, res.stderr
    assert "median" in res.stdout
