import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { MPI_IMPLEMENTATIONS, SERIES_COLORS, IMPL_LABELS } from "../constants.js";

/** Pivots rows (already filtered to one grid+scenario) into
 * [{nprocs, <implementation>: value, ...}] for a recharts LineChart. */
function pivotByProcesses(rows, valueKey) {
  const byProcs = {};
  for (const r of rows) {
    if (!MPI_IMPLEMENTATIONS.includes(r.implementation)) continue;
    const key = r.nprocs;
    byProcs[key] = byProcs[key] || { nprocs: key };
    byProcs[key][r.implementation] = r[valueKey];
  }
  return Object.values(byProcs).sort((a, b) => a.nprocs - b.nprocs);
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: "#fff", border: "1px solid #e6ddc8", borderRadius: 8,
      padding: "8px 12px", fontSize: 12, boxShadow: "0 6px 20px -8px rgba(0,0,0,0.2)",
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label} process{label === 1 ? "" : "es"}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, display: "inline-block" }} />
            {IMPL_LABELS[p.dataKey]}
          </span>
          <strong>{typeof p.value === "number" ? p.value.toFixed(4) : "N/A"}{unit}</strong>
        </div>
      ))}
    </div>
  );
}

export function LegendRow() {
  return (
    <div className="legend-row">
      {MPI_IMPLEMENTATIONS.map((impl) => (
        <span className="legend-chip" key={impl}>
          <span className="dot" style={{ background: SERIES_COLORS[impl] }} />
          {IMPL_LABELS[impl]}
        </span>
      ))}
    </div>
  );
}

export function MetricChart({ rows, valueKey, unit = "", height = 220 }) {
  const data = pivotByProcesses(rows, valueKey);
  const hasData = data.length > 0 && data.some((d) =>
    MPI_IMPLEMENTATIONS.some((impl) => d[impl] != null));

  if (!hasData) {
    return <div className="empty-state" style={{ padding: "24px 8px" }}>No data for this configuration.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 12, bottom: 5, left: -10 }}>
        <CartesianGrid stroke="#efe8d8" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="nprocs" tick={{ fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#e6ddc8" }} />
        <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#e6ddc8" }} width={44} />
        <Tooltip content={<CustomTooltip unit={unit} />} />
        {MPI_IMPLEMENTATIONS.map((impl) => (
          <Line key={impl} type="monotone" dataKey={impl} stroke={SERIES_COLORS[impl]}
                strokeWidth={2.25} dot={{ r: 3.5 }} activeDot={{ r: 5 }} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function MetricSmallMultiples({ rowsByGrid, valueKey, unit = "" }) {
  const grids = Object.keys(rowsByGrid);
  return (
    <div className="multiples-grid">
      {grids.map((grid) => (
        <div className="multiple-panel" key={grid}>
          <h3>{grid}</h3>
          <div className="n">{rowsByGrid[grid].length} configurations</div>
          <MetricChart rows={rowsByGrid[grid]} valueKey={valueKey} unit={unit} height={190} />
        </div>
      ))}
    </div>
  );
}
