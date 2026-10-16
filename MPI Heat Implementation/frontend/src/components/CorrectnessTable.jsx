import { IMPL_LABELS, TOLERANCE } from "../constants.js";

export default function CorrectnessTable({ rows }) {
  const relevant = rows
    .filter((r) => r.implementation !== "sequential")
    .sort((a, b) => a.rows - b.rows || a.scenario.localeCompare(b.scenario) || a.nprocs - b.nprocs
      || a.implementation.localeCompare(b.implementation));

  const pass = (r) => r.max_abs_err != null && r.max_abs_err <= TOLERANCE && r.checksums_match;
  const passCount = relevant.filter(pass).length;

  return (
    <div className="card">
      <h2>Correctness</h2>
      <p className="subtitle">
        Before timing anything, every MPI run gathers its field on rank 0 and compares it cell by cell
        with a sequential run on the same grid, scenario, seed, r and step count. The run exits with an
        error if the difference is above {TOLERANCE.toExponential(0)}. Every variant does the same
        arithmetic per cell, so the expected difference is exactly 0. Each trial's checksum must also
        match.
        {relevant.length > 0 && <strong> {passCount}/{relevant.length} configurations pass.</strong>}
        {" "}The analytic check (error against the exact decaying-sine solution, second-order convergence)
        is in <code>scripts/validate.py</code> and the Live demo tab.
      </p>
      {relevant.length === 0 ? (
        <div className="empty-state">No measured results available yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Implementation</th>
              <th>Grid</th>
              <th>Processes</th>
              <th>Process grid</th>
              <th>Scenario</th>
              <th>Max abs error vs sequential</th>
              <th>Trial checksums</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {relevant.map((r, i) => (
              <tr key={i}>
                <td>{IMPL_LABELS[r.implementation] || r.implementation}</td>
                <td>{r.rows}×{r.cols}</td>
                <td>{r.nprocs}{r.oversubscribed ? " *" : ""}</td>
                <td>{r.proc_grid}</td>
                <td>{r.scenario.replace("_", " ")}</td>
                <td>{r.max_abs_err != null ? r.max_abs_err.toExponential(1) : "N/A"}</td>
                <td>{r.checksums_match ? "identical" : "differ"}</td>
                <td><span className={`status-pill ${pass(r) ? "pass" : "fail"}`}>{pass(r) ? "PASS" : "FAIL"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {relevant.some((r) => r.oversubscribed) && (
        <p className="subtitle" style={{ marginTop: 10, marginBottom: 0 }}>* oversubscribed (more ranks than physical cores)</p>
      )}
    </div>
  );
}
