export default function KpiTile({ label, value, sub, accent }) {
  return (
    <div className="kpi-tile">
      <div className="accent" style={{ background: accent || "var(--mint)" }} />
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
