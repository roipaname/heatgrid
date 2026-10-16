// Validated categorical palette (dataviz skill: light mode, 4 slots, CVD-safe
// in this fixed order). Series identity always maps to this order.
export const MPI_IMPLEMENTATIONS = [
  "slab_blocking", "slab_nonblocking", "cartesian_blocking", "cartesian_nonblocking",
];

export const SERIES_COLORS = {
  slab_blocking: "#2a78d6",
  slab_nonblocking: "#eb6834",
  cartesian_blocking: "#1baf7a",
  cartesian_nonblocking: "#eda100",
};

export const IMPL_LABELS = {
  sequential: "Sequential",
  slab_blocking: "1D slab · blocking",
  slab_nonblocking: "1D slab · non-blocking",
  cartesian_blocking: "2D Cartesian · blocking",
  cartesian_nonblocking: "2D Cartesian · non-blocking",
};

// src/heatgrid/checks.py: MPI vs sequential must agree to within this (in practice it's exactly 0)
export const TOLERANCE = 1e-12;
