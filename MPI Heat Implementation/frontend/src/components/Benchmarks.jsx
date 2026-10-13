import { useMemo, useState } from "react";
import { MetricSmallMultiples, LegendRow } from "./Charts.jsx";

const METRICS = [
  { key: "median_s", label: "Runtime", unit: "s",
    subtitle: "Median timestep-loop wall-clock time (10 trials, first discarded)." },
  { key: "speedup", label: "Speedup", unit: "×",
    subtitle: "Relative to the optimized sequential baseline, not the 1-process MPI run." },
  { key: "parallel_efficiency", label: "Efficiency", unit: "",
    subtitle: "Speedup / processes. Values above 1.0 at p=4 reflect oversubscribing this machine's 2 physical cores." },
  { key: "median_comm_fraction", label: "Comm. fraction", unit: "",
    subtitle: "Communication time / total timestep-loop time (median across trials)." },
];

export default function Benchmarks({ rows }) {
  const scenarios = useMemo(() => [...new Set(rows.map((r) => r.scenario))].sort(), [rows]);
  const [scenario, setScenario] = useState(scenarios[0] || "");
  const [metricKey, setMetricKey] = useState("median_s");

  const active = scenarios.includes(scenario) ? scenario : scenarios[0];
  const metric = METRICS.find((m) => m.key === metricKey);

  const scoped = rows.filter((r) => r.scenario === active);
  const rowsByGrid = useMemo(() => {
    const grouped = {};
    for (const r of scoped) {
      const key = `${r.rows}×${r.cols}`;
      (grouped[key] = grouped[key] || []).push(r);
    }
    return Object.fromEntries(
      Object.entries(grouped).sort((a, b) => a[1][0].rows - b[1][0].rows)
    );
  }, [scoped]);

  if (rows.length === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          No measured results available yet.<br />
          Run <code>python backend/run_matrix.py scaling</code>, then{" "}
          <code>python backend/export_json.py</code>.
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Scaling behaviour</h2>
      <p className="subtitle">
        RQ1: does 2D Cartesian outperform 1D slab at low process counts? RQ2: does non-blocking
        exchange reduce runtime consistent with measured communication time? One panel per grid
        size, all four MPI implementations plotted against process count.
      </p>

      <div className="filters" style={{ marginBottom: 18 }}>
        <div className="filter-group">
          <label>Scenario</label>
          <div className="segmented">
            {scenarios.map((s) => (
              <button key={s} className={s === active ? "active" : ""} onClick={() => setScenario(s)}>
                {s.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-group">
          <label>Metric</label>
          <div className="segmented">
            {METRICS.map((m) => (
              <button key={m.key} className={m.key === metricKey ? "active" : ""} onClick={() => setMetricKey(m.key)}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <LegendRow />
      <p className="subtitle" style={{ marginTop: -8 }}>{metric.subtitle}</p>
      <MetricSmallMultiples rowsByGrid={rowsByGrid} valueKey={metric.key} unit={metric.unit} />
    </div>
  );
}
