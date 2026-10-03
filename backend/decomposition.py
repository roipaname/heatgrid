"""Shared 1D block distribution used by both the slab and Cartesian
decompositions, so both partition any one axis the same way."""


def block_distribute(n, nprocs, rank):
    """Splits n items over nprocs ranks, remainder spread across the first
    ranks. Returns (local_n, global_start)."""
    base, remainder = divmod(n, nprocs)
    local_n = base + (1 if rank < remainder else 0)
    start = rank * base + min(rank, remainder)
    return local_n, start
