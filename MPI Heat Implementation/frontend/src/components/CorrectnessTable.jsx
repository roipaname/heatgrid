import { ABS_TOLERANCE, REL_TOLERANCE, IMPL_LABELS } from "../constants.js";

export default function CorrectnessTable({ rows }) {
  const relevant = rows
    .filter((r) => r.implementation !== "sequential" && r.status === "ok")
    .sort((a, b) => a.rows - b.rows || a.nprocs - b.nprocs || a.implementation.localeCompare(b.implementation));

  const passCount = relevant.filter((r) =>
    r.max_abs_err != null && (r.max_abs_err <= ABS_TOLERANCE || r.max_rel_err <= REL_TOLERANCE)
  ).length;

  return (
    <div className="card">
      <h2>Correctness</h2>
      <p className="subtitle">
        Every MPI run is compared cell-by-cell against the sequential reference for the same
        grid, scenario, seed and timestep count. PASS if max absolute error ≤ {ABS_TOLERANCE.toExponential(0)}{" "}
        or max relative error ≤ {REL_TOLERANCE.toExponential(0)}, since floating-point reduction
        order differs across decompositions, so exact bit-equality isn't the bar.
        {relevant.length > 0 && <strong> {passCount}/{relevant.length} checks pass.</strong>}
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
              <th>Scenario</th>
              <th>Max abs error</th>
              <th>Mean abs error</th>
              <th>Max rel error</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {relevant.map((r, i) => {
              const pass = r.max_abs_err != null &&
                (r.max_abs_err <= ABS_TOLERANCE || r.max_rel_err <= REL_TOLERANCE);
              return (
                <tr key={i}>
                  <td>{IMPL_LABELS[r.implementation] || r.implementation}</td>
                  <td>{r.rows}×{r.cols}</td>
                  <td>{r.nprocs}</td>
                  <td>{r.scenario.replace("_", " ")}</td>
                  <td>{r.max_abs_err != null ? r.max_abs_err.toExponential(2) : "N/A"}</td>
                  <td>{r.mean_abs_err != null ? r.mean_abs_err.toExponential(2) : "N/A"}</td>
                  <td>{r.max_rel_err != null ? r.max_rel_err.toExponential(2) : "N/A"}</td>
                  <td><span className={`status-pill ${pass ? "pass" : "fail"}`}>{pass ? "PASS" : "FAIL"}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
