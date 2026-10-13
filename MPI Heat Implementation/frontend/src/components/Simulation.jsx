import { useEffect, useRef, useState } from "react";
import { heatColor } from "../heatColor.js";

const SIZE = 60; // matches scenario_previews.json preview resolution
const R_MAX = 0.25;

/** Exact port of backend/heat.py::stencil_update -- same five-point FTCS
 * formula, same boundary-preservation rule (outermost ring never updated). */
function stepStencil(u, size, r) {
  const next = u.slice();
  for (let i = 1; i < size - 1; i++) {
    for (let j = 1; j < size - 1; j++) {
      const idx = i * size + j;
      const c = u[idx];
      const n = u[idx - size];
      const s = u[idx + size];
      const w = u[idx - 1];
      const e = u[idx + 1];
      next[idx] = c + r * (n + s + w + e - 4 * c);
    }
  }
  return next;
}

function flatten(values) {
  const size = values.length;
  const out = new Float64Array(size * size);
  for (let i = 0; i < size; i++) for (let j = 0; j < size; j++) out[i * size + j] = values[i][j];
  return out;
}

function SimCanvas({ field, size, min, max }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(size, size);
    const range = max - min || 1;
    for (let idx = 0; idx < size * size; idx++) {
      const t = (field[idx] - min) / range;
      const [r, g, b] = heatColor(t);
      img.data[idx * 4] = r;
      img.data[idx * 4 + 1] = g;
      img.data[idx * 4 + 2] = b;
      img.data[idx * 4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
  }, [field, size, min, max]);
  return <canvas ref={canvasRef} style={{ imageRendering: "pixelated" }} />;
}

function blockDistribute(n, nprocs, rank) {
  const base = Math.floor(n / nprocs);
  const remainder = n % nprocs;
  const localN = base + (rank < remainder ? 1 : 0);
  const start = rank * base + Math.min(rank, remainder);
  return [localN, start];
}

const PROCESS_GRID_DIMS = { 1: [1, 1], 2: [1, 2], 4: [2, 2] };
const RANK_COLORS = ["#3f7c6e", "#c8582f", "#ad7b1f", "#6b7fb3"];

function DecompositionDiagram({ decomposition, processes, rows, cols }) {
  const [pRow, pCol] = decomposition === "slab" ? [processes, 1] : PROCESS_GRID_DIMS[processes];
  const cells = [];
  for (let pr = 0; pr < pRow; pr++) {
    for (let pc = 0; pc < pCol; pc++) {
      const rank = pr * pCol + pc;
      const [localRows] = blockDistribute(rows, pRow, pr);
      const [localCols] = blockDistribute(cols, pCol, pc);
      cells.push({ rank, pr, pc, localRows, localCols });
    }
  }
  return (
    <div>
      <div className="decomp-grid" style={{ gridTemplateColumns: `repeat(${pCol}, 1fr)` }}>
        {cells.map((c) => (
          <div key={c.rank} className="decomp-cell" style={{ background: RANK_COLORS[c.rank % RANK_COLORS.length] }}>
            P{c.rank}&nbsp;·&nbsp;{c.localRows}×{c.localCols}
          </div>
        ))}
      </div>
      <p className="subtitle" style={{ marginTop: 10, marginBottom: 0 }}>
        {decomposition === "slab"
          ? "Each rank owns a horizontal band (full width) and exchanges a one-cell halo row with its row-neighbours only, above and below."
          : "Each rank owns a rectangular block and exchanges a one-cell halo with up to four neighbours: rows via contiguous buffers (above and below), columns via a strided MPI derived datatype (left and right)."}
      </p>
    </div>
  );
}

export default function Simulation({ previews }) {
  const scenarios = previews ? Object.keys(previews) : [];
  const [scenario, setScenario] = useState("");
  const [r, setR] = useState(0.2);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(2); // steps per frame
  const [field, setField] = useState(null);
  const [step, setStep] = useState(0);
  const [decomposition, setDecomposition] = useState("cartesian");
  const [processes, setProcesses] = useState(4);

  useEffect(() => {
    if (!scenario && scenarios.length) setScenario(scenarios[0]);
  }, [scenarios, scenario]);

  const reset = () => {
    if (!previews || !previews[scenario]) return;
    setField(flatten(previews[scenario].values));
    setStep(0);
    setRunning(false);
  };

  useEffect(reset, [scenario, previews]);

  useEffect(() => {
    if (!running || !field) return;
    let raf;
    const tick = () => {
      setField((prev) => {
        let f = prev;
        for (let k = 0; k < speed; k++) f = stepStencil(f, SIZE, r);
        return f;
      });
      setStep((s) => s + speed);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, speed, r]);

  if (!previews || scenarios.length === 0) {
    return (
      <div className="card">
        <div className="empty-state">Run <code>python backend/export_json.py</code> to generate scenario fields to simulate.</div>
      </div>
    );
  }

  const preview = previews[scenario];
  const bounds = preview ? { min: preview.min, max: preview.max } : { min: 0, max: 1 };

  return (
    <>
      <div className="card">
        <h2>Live diffusion simulation<span className="badge">runs in your browser</span></h2>
        <p className="subtitle">
          The exact five-point FTCS stencil from <code>backend/heat.py</code>, re-implemented in
          JavaScript and run client-side on the real seeded scenario field (60×60 preview
          resolution), with no server round-trip. This is what every implementation computes each
          timestep; they differ only in how the grid is split and halos exchanged.
        </p>

        <div className="sim-layout">
          <div>
            <div className="control-row">
              <label>Scenario</label>
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {scenarios.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
            <div className="control-row">
              <label>r = {r.toFixed(2)}</label>
              <input type="range" min="0.02" max={R_MAX} step="0.01" value={r}
                     onChange={(e) => setR(parseFloat(e.target.value))} style={{ flex: 1 }} />
            </div>
            <div className="control-row">
              <label>Speed</label>
              <input type="range" min="1" max="8" step="1" value={speed}
                     onChange={(e) => setSpeed(parseInt(e.target.value, 10))} style={{ flex: 1 }} />
              <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>{speed} steps/frame</span>
            </div>
            <div className="control-row">
              <button className="btn primary" onClick={() => setRunning((r2) => !r2)}>
                {running ? "Pause" : "Play"}
              </button>
              <button className="btn" onClick={reset}>Reset</button>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                t = {step}
              </span>
            </div>
            <p className="subtitle" style={{ marginBottom: 0 }}>
              Stability requires r ≤ {R_MAX}. Boundary ring stays fixed (Dirichlet) the whole run,
              exactly as in the benchmarked solver.
            </p>
          </div>

          <div className="sim-canvas-wrap">
            {field && <SimCanvas field={field} size={SIZE} min={bounds.min} max={bounds.max} />}
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Domain decomposition geometry</h2>
        <p className="subtitle">
          How the same grid gets split across processes. Built from <code>MPI_Dims_create</code>-style
          process grids and the exact block-distribution rule in <code>backend/decomposition.py</code>.
        </p>
        <div className="filters" style={{ marginBottom: 16 }}>
          <div className="filter-group">
            <label>Decomposition</label>
            <div className="segmented">
              <button className={decomposition === "slab" ? "active" : ""} onClick={() => setDecomposition("slab")}>1D slab</button>
              <button className={decomposition === "cartesian" ? "active" : ""} onClick={() => setDecomposition("cartesian")}>2D Cartesian</button>
            </div>
          </div>
          <div className="filter-group">
            <label>Processes</label>
            <div className="segmented">
              {[1, 2, 4].map((p) => (
                <button key={p} className={processes === p ? "active" : ""} onClick={() => setProcesses(p)}>{p}</button>
              ))}
            </div>
          </div>
        </div>
        <DecompositionDiagram decomposition={decomposition} processes={processes} rows={SIZE} cols={SIZE} />
      </div>
    </>
  );
}
