import KpiTile from "./KpiTile.jsx";
import { IMPL_LABELS, SERIES_COLORS } from "../constants.js";

export default function Dashboard({ summary }) {
  if (!summary || summary.total_configurations === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          No measured results available yet.<br />
          Run <code>python backend/run_matrix.py smoke</code> (or <code>scaling</code> /{" "}
          <code>full</code>), then <code>python backend/export_json.py</code>.
        </div>
      </div>
    );
  }

  const passRate = summary.correctness_checked
    ? Math.round((summary.correctness_passed / summary.correctness_checked) * 100)
    : null;

  const best = summary.best_speedup;

  return (
    <>
      <div className="kpi-grid">
        <KpiTile label="Configurations run" value={summary.ok_configurations}
                 sub={summary.failed_configurations ? `${summary.failed_configurations} failed` : "0 failed"}
                 accent="var(--mint)" />
        <KpiTile label="Correctness pass rate" value={passRate !== null ? `${passRate}%` : "N/A"}
                 sub={`${summary.correctness_passed}/${summary.correctness_checked} checks vs. sequential`}
                 accent="var(--gold)" />
        <KpiTile label="Grid sizes covered" value={summary.grid_sizes.length}
                 sub={summary.grid_sizes.join(", ")}
                 accent="var(--coral)" />
        <KpiTile label="Best measured speedup" value={best ? `${best.speedup.toFixed(2)}×` : "N/A"}
                 sub={best ? `${IMPL_LABELS[best.implementation]}, p=${best.nprocs}` : "no MPI runs yet"}
                 accent={best ? SERIES_COLORS[best.implementation] : "var(--mint)"} />
      </div>

      <div className="card">
        <h2>Coverage</h2>
        <p className="subtitle">What the current dataset in <code>results/raw/benchmark.csv</code> actually spans.</p>
        <table>
          <tbody>
            <tr><th>Implementations</th><td>{summary.implementations.map((i) => IMPL_LABELS[i] || i).join(", ")}</td></tr>
            <tr><th>Process counts</th><td>{summary.process_counts.join(", ")}</td></tr>
            <tr><th>Grid sizes</th><td>{summary.grid_sizes.join(", ")}</td></tr>
            <tr><th>Scenarios</th><td>{summary.scenarios.join(", ")}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>About this study</h2>
        <p className="subtitle" style={{ marginBottom: 0 }}>
          Explicit five-point stencil solver for the 2D heat equation, comparing 1D slab vs.
          2D Cartesian domain decomposition and blocking vs. non-blocking halo exchange at
          low process counts (1–4) on a single 2-physical-core machine. Speedup is always
          measured against the optimized sequential baseline, never the 1-process MPI run.
          Synthetic scenarios represent qualitative Johannesburg-inspired thermal structure,
          not measured temperatures. See the <strong>Benchmarks</strong> tab for RQ1/RQ2 evidence,
          <strong> Correctness</strong> for validation, and <strong>Simulation</strong> to see the
          stencil and decomposition geometry directly.
        </p>
      </div>
    </>
  );
}
