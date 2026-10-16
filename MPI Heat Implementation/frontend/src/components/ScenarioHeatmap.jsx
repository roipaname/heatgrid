import { useEffect, useRef } from "react";
import { heatColor } from "../heatColor.js";

function Field({ values, size, min, max }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!values) return;
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
  }, [values, size, min, max]);

  return <canvas ref={canvasRef} style={{ imageRendering: "pixelated" }} />;
}

function Tile({ scenario, preview }) {
  const { size, min, max } = preview;
  return (
    <div className="scenario-tile">
      <div className="pair">
        <div><Field values={preview.values} size={size} min={min} max={max} /><div className="caption">start</div></div>
        {preview.after && (
          <div><Field values={preview.after} size={size} min={min} max={max} />
            <div className="caption">after {preview.after_steps} steps</div></div>
        )}
      </div>
      <div className="label">{scenario.replace("_", " ")}</div>
      <div className="caption">synthetic field, not measured temperature (same colour scale in both)</div>
    </div>
  );
}

export default function ScenarioHeatmap({ previews }) {
  const scenarios = previews ? Object.keys(previews) : [];
  return (
    <div className="card">
      <h2>Scenario fields</h2>
      <p className="subtitle">
        Seeded synthetic initial conditions from <code>src/heatgrid/core/scenarios.py</code> (unit square,
        fixed boundaries), shown at 60x60 before and after diffusion with the sequential solver. These
        are qualitative thermal patterns, not real Johannesburg temperature observations.
      </p>
      {scenarios.length === 0 ? (
        <div className="empty-state">Run <code>python scripts/export_frontend.py</code> to generate previews.</div>
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
