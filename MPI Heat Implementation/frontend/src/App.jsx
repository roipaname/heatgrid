import { useEffect, useMemo, useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import Benchmarks from "./components/Benchmarks.jsx";
import CorrectnessTable from "./components/CorrectnessTable.jsx";
import Simulation from "./components/Simulation.jsx";
import ScenarioHeatmap from "./components/ScenarioHeatmap.jsx";
import LiveDemo from "./components/LiveDemo.jsx";
import {
  DashboardIcon, BenchmarksIcon, CorrectnessIcon, SimulationIcon, ScenariosIcon, TerminalIcon,
} from "./components/Icons.jsx";

const TABS = [
  { key: "dashboard", label: "Dashboard", Icon: DashboardIcon },
  { key: "demo", label: "Live demo", Icon: TerminalIcon },
  { key: "benchmarks", label: "Benchmarks", Icon: BenchmarksIcon },
  { key: "correctness", label: "Correctness", Icon: CorrectnessIcon },
  { key: "simulation", label: "Simulation", Icon: SimulationIcon },
  { key: "scenarios", label: "Scenarios", Icon: ScenariosIcon },
];

const getJson = (url) => fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));

export default function App() {
  const [datasets, setDatasets] = useState(null);
  const [datasetName, setDatasetName] = useState(null);
  const [results, setResults] = useState(null);
  const [summary, setSummary] = useState(null);
  const [previews, setPreviews] = useState(null);
  const [tab, setTab] = useState("dashboard");

  useEffect(() => {
    getJson("/data/datasets.json").then((d) => {
      setDatasets(d);
      setDatasetName(d[0]?.name ?? null);
      if (!d.length) setResults([]);
    }).catch(() => { setDatasets([]); setResults([]); });
    getJson("/data/scenario_previews.json").then(setPreviews).catch(() => setPreviews({}));
  }, []);

  useEffect(() => {
    if (!datasetName) return;
    getJson(`/data/${datasetName}/results.json`).then(setResults).catch(() => setResults([]));
    getJson(`/data/${datasetName}/summary.json`).then(setSummary).catch(() => setSummary(null));
  }, [datasetName]);

  const rows = useMemo(() => results || [], [results]);
  const dataset = (datasets || []).find((d) => d.name === datasetName);

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
        {datasets && datasets.length > 0 && (
          <div className="header-meta">
            <label className="dataset-pick">
              <span>Dataset</span>
              <select value={datasetName || ""} onChange={(e) => setDatasetName(e.target.value)}>
                {datasets.map((d) => <option key={d.name} value={d.name}>{d.label}</option>)}
              </select>
            </label>
            {summary && <span className="pill"><strong>{summary.ok_configurations}</strong> configs</span>}
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

      {tab === "dashboard" && <Dashboard summary={summary} dataset={dataset} />}
      {tab === "demo" && <LiveDemo />}
      {tab === "benchmarks" && <Benchmarks rows={rows} dataset={dataset} />}
      {tab === "correctness" && <CorrectnessTable rows={rows} />}
      {tab === "simulation" && <Simulation previews={previews} />}
      {tab === "scenarios" && <ScenarioHeatmap previews={previews} />}
    </div>
  );
}
