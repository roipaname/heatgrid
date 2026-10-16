import KpiTile from "./KpiTile.jsx";
import { IMPL_LABELS, SERIES_COLORS } from "../constants.js";

export default function Dashboard({ summary, dataset }) {
  if (!summary || summary.total_configurations === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          No measured results available yet.<br />
          Run <code>python scripts/run_experiments.py config/full.json</code>, then{" "}
          <code>python scripts/summarise.py</code> and <code>python scripts/export_frontend.py</code>.
        </div>
      </div>
    );
  }

  const passRate = summary.correctness_checked
    ? Math.round((summary.correctness_passed / summary.correctness_checked) * 100)
    : null;
  const best = summary.best_speedup;
  const env = summary.run?.environment || {};

  return (
    <>
      <div className="kpi-grid">
        <KpiTile label="Configurations" value={summary.ok_configurations}
                 sub={`${summary.trials} measured trials each (+ warm-up), ${summary.steps} steps`}
                 accent="var(--mint)" />
        <KpiTile label="Match sequential exactly" value={passRate !== null ? `${passRate}%` : "N/A"}
                 sub={`${summary.correctness_passed}/${summary.correctness_checked} MPI configurations, max abs error 0`}
                 accent="var(--gold)" />
        <KpiTile label="Grid sizes" value={summary.grid_sizes.length}
                 sub={summary.grid_sizes.join(", ")}
                 accent="var(--coral)" />
        <KpiTile label="Best speedup (not oversubscribed)" value={best ? `${best.speedup.toFixed(2)}×` : "N/A"}
                 sub={best ? `${IMPL_LABELS[best.implementation]}, p=${best.nprocs}, ${best.rows}×${best.cols}` : "no MPI runs yet"}
                 accent={best ? SERIES_COLORS[best.implementation] : "var(--mint)"} />
      </div>

      <div className="card">
        <h2>This dataset</h2>
        <p className="subtitle">{dataset?.note}</p>
        <table>
          <tbody>
            <tr><th>Machine</th><td>{dataset?.machine}</td></tr>
            {env.cpu && <tr><th>CPU (recorded)</th><td>{env.cpu}</td></tr>}
            {env.python && <tr><th>Software</th><td>Python {env.python}, NumPy {env.numpy}, mpi4py {env.mpi4py}, {env.mpi_library}</td></tr>}
            <tr><th>Raw file</th><td><code>results/raw/{summary.source}</code></td></tr>
            {summary.run?.wall_seconds && <tr><th>Total run time</th><td>{Math.round(summary.run.wall_seconds / 60)} min, {summary.run.failed} failed</td></tr>}
            <tr><th>Implementations</th><td>{summary.implementations.map((i) => IMPL_LABELS[i] || i).join(", ")}</td></tr>
            <tr><th>Process counts</th><td>{summary.process_counts.join(", ")}
              {summary.oversubscribed_configurations > 0 && ` (${summary.oversubscribed_configurations} configurations oversubscribed: more ranks than physical cores)`}</td></tr>
            <tr><th>Scenarios</th><td>{summary.scenarios.map((s) => s.replace("_", " ")).join(", ")}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>About this study</h2>
        <p className="subtitle" style={{ marginBottom: 0 }}>
          An explicit five-point stencil solver for the 2D heat equation. It compares 1D slab
          with 2D Cartesian domain decomposition (RQ1), and blocking with non-blocking halo exchange
          (RQ2), at low process counts on one shared-memory machine. Speedup is always measured
          against the sequential baseline, never against the 1-process MPI run. Runtimes are medians
          of repeated trials, taken from the slowest rank. The scenarios are synthetic,
          Johannesburg-inspired thermal patterns, not measured temperatures.
          Use <strong>Live demo</strong> to run the programs, <strong>Benchmarks</strong> for the
          RQ1/RQ2 evidence and <strong>Correctness</strong> for validation.
        </p>
      </div>
    </>
  );
}
