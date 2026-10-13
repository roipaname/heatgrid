# Methodology

## Timing

`runtime_seconds` (column `runN_s` / `median_s` in the CSV) times only the timestep loop.
Scenario field construction, buffer allocation and CSV writing are excluded. MPI runtimes use
`MPI.Wtime()`; the sequential baseline uses `time.perf_counter()` since it never calls
`MPI_Init`. For MPI runs, `comm.reduce(..., op=MPI.MAX, root=0)` is used so the reported time is
the slowest rank, not rank 0's local time.

`communication_seconds` (`median_comm_s`) accumulates time spent inside the halo-exchange calls
only (`Sendrecv`, or `Isend`/`Irecv` + `Waitall`), also MAX-reduced across ranks.

## Warm-up and trials

Each configuration runs `warmup` (default 1) discarded iterations followed by `trials` (default
10) measured iterations. `median_s` and `iqr_s` are reported rather than a single best/first
time, per standard guidance against over-optimistic single-sample benchmarking.

## Correctness

Every MPI configuration is compared cell-by-cell against a sequential run with the same grid,
scenario, seed, `r` and timestep count (`backend/validate.py::compare_fields`), computed once per
configuration (not per trial, and never inside the timed region). Reported: max absolute error,
mean absolute error, max relative error (safe denominator `max(|reference|, 1e-12)`). A run
passes if max absolute error ≤ 1e-8 or max relative error ≤ 1e-6, since floating-point reduction
order differs across decompositions, so exact bit-equality isn't the bar.

Independently, `backend/validate_analytic.py` runs the sequential solver on a decaying-sine
initial condition (`u(x,y,0) = sin(pi x) sin(pi y)`, zero Dirichlet boundary) and compares against
the closed-form solution `u(x,y,t) = sin(pi x) sin(pi y) exp(-2 pi^2 alpha t)`, measuring true
numerical error rather than only cross-implementation agreement.

## Boundary handling

The outermost ring of the global domain is a fixed Dirichlet boundary. Both solver buffers are
seeded with boundary values at setup and the stencil update loop never touches boundary rows/
columns (see `row_lo`/`row_hi`/`col_lo`/`col_hi` in `mpi_slab.py`/`mpi_cartesian.py`), so boundary
values persist for the whole run without being re-copied every step. This is identical across all
five implementations.

## Non-blocking overlap

The non-blocking variants post `Irecv`/`Isend`, then update the *strict interior* (cells that
don't depend on any value received this step) before calling `Waitall`, then update the
halo-dependent boundary layer. Whether the underlying MPI implementation actually overlaps that
computation with the transfer (rather than blocking on send/recv progression) is treated as an
empirical question (RQ2), not assumed.

## Derived datatype

2D Cartesian west/east halo columns are non-contiguous in row-major storage (elements are
`local_cols + 2` doubles apart). `MPI.DOUBLE.Create_vector(...)` describes this stride directly so
a column can be sent/received in one call without manually packing it into a temporary buffer.
North/south rows are contiguous and use plain buffers. The 5-point stencil never reads diagonal/
corner halo cells, so north/south and west/east exchanges never need to coordinate on corners.

## Oversubscription

The target machine has 2 physical cores. 4-process runs are intentionally oversubscribed; this is
recorded (`oversubscribed` column) rather than hidden, and reported as a stress/functional data
point rather than scaling evidence.
