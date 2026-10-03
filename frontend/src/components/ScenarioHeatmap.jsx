import { useEffect, useRef } from "react";
import { heatColor } from "../heatColor.js";

function Tile({ scenario, preview }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!preview) return;
    const { size, min, max, values } = preview;
    const canvas = canvasRef.current;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(size, size);
    const range = max - min || 1;
    for (let i = 0; i < size; i++) {
      for (let j = 0; j < size; j++) {
        const t = (values[i][j] - min) / range;
        const [r, g, b] = heatColor(t);
        const idx = (i * size + j) * 4;
        img.data[idx] = r;
        img.data[idx + 1] = g;
        img.data[idx + 2] = b;
        img.data[idx + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }, [preview]);

  return (
    <div className="scenario-tile">
      <canvas ref={canvasRef} style={{ imageRendering: "pixelated" }} />
      <div className="label">{scenario.replace("_", " ")}</div>
      <div className="caption">synthetic model field · not measured temperature</div>
    </div>
  );
}

export default function ScenarioHeatmap({ previews }) {
  const scenarios = previews ? Object.keys(previews) : [];
  return (
    <div className="card">
      <h2>Scenario fields</h2>
      <p className="subtitle">
        Seeded synthetic initial conditions (unit square, Dirichlet boundaries). These are
        qualitative thermal structures, not real Johannesburg temperature observations.
      </p>
      {scenarios.length === 0 ? (
        <div className="empty-state">Run <code>python backend/export_json.py</code> to generate previews.</div>
      ) : (
        <div className="scenario-grid">
          {scenarios.map((s) => (
            <Tile key={s} scenario={s} preview={previews[s]} />
          ))}
        </div>
      )}
    </div>
  );
}
