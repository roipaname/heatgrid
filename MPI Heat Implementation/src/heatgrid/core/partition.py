"""Block partitioning shared by the slab and Cartesian versions."""

MIN_LOCAL = 3  # fewer rows/cols per rank breaks the boundary handling


def block_range(n, parts, index):
    # first (n % parts) blocks get one extra item
    base, extra = divmod(n, parts)
    count = base + (1 if index < extra else 0)
    start = index * base + min(index, extra)
    return count, start


def check_split(n, parts, axis):
    if n // parts < MIN_LOCAL:
        raise ValueError(f"{n} {axis} over {parts} ranks leaves fewer than "
                         f"{MIN_LOCAL} {axis} per rank, use a bigger grid or fewer processes")
