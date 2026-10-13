import { useEffect, useMemo, useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import Benchmarks from "./components/Benchmarks.jsx";
import CorrectnessTable from "./components/CorrectnessTable.jsx";
import Simulation from "./components/Simulation.jsx";
import ScenarioHeatmap from "./components/ScenarioHeatmap.jsx";
import { DashboardIcon, BenchmarksIcon, CorrectnessIcon, SimulationIcon, ScenariosIcon } from "./components/Icons.jsx";

const TABS = [
  { key: "dashboard", label: "Dashboard", Icon: DashboardIcon },
  { key: "benchmarks", label: "Benchmarks", Icon: BenchmarksIcon },
  { key: "correctness", label: "Correctness", Icon: CorrectnessIcon },
  { key: "simulation", label: "Simulation", Icon: SimulationIcon },
  { key: "scenarios", label: "Scenarios", Icon: ScenariosIcon },
];

export default function App() {
  const [results, setResults] = useState(null);
  const [summary, setSummary] = useState(null);
  const [previews, setPreviews] = useState(null);
  const [tab, setTab] = useState("dashboard");

  useEffect(() => {
    fetch("/data/results.json").then((r) => r.json()).then(setResults).catch(() => setResults([]));
    fetch("/data/summary.json").then((r) => r.json()).then(setSummary).catch(() => setSummary(null));
    fetch("/data/scenario_previews.json").then((r) => r.json()).then(setPreviews).catch(() => setPreviews({}));
  }, []);

  const okRows = useMemo(() => (results || []).filter((r) => r.status === "ok"), [results]);

  if (results === null) {
    return <div id="app-shell"><div className="empty-state">Loading…</div></div>;
  }

  return (
    <div id="app-shell">
      <header className="app-header">
        <div className="brand">
          <img src="/logo.png" alt="HeatGrid" />
          <div>
            <h1>HeatGrid</h1>
            <p>Resource-aware MPI heat diffusion, using domain decomposition for Johannesburg urban heat scenarios</p>
          </div>
        </div>
        {summary && summary.total_configurations > 0 && (
          <div className="header-meta">
            <span className="pill"><strong>{summary.ok_configurations}</strong> configs</span>
            <span className="pill"><strong>{summary.grid_sizes.length}</strong> grid sizes</span>
            {summary.correctness_checked > 0 && (
              <span className="pill">
                <strong>{Math.round((summary.correctness_passed / summary.correctness_checked) * 100)}%</strong> correctness
              </span>
            )}
          </div>
        )}
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
            <t.Icon />{t.label}
          </button>
        ))}
      </nav>

      {tab === "dashboard" && <Dashboard summary={summary} />}
      {tab === "benchmarks" && <Benchmarks rows={okRows} />}
      {tab === "correctness" && <CorrectnessTable rows={okRows} />}
      {tab === "simulation" && <Simulation previews={previews} />}
      {tab === "scenarios" && <ScenarioHeatmap previews={previews} />}
    </div>
  );
}
