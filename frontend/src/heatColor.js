// Cool (mint) -> warm background -> hot (coral/gold): a restrained scientific
// heat scale rather than a saturated rainbow. Shared by the scenario preview
// heatmaps and the live simulation canvas.
const STOPS = [
  [95, 156, 143],   // mint
  [250, 246, 239],  // warm off-white
  [201, 154, 58],   // gold
  [217, 119, 87],   // coral
];

export function heatColor(t) {
  const n = STOPS.length - 1;
  const scaled = Math.min(Math.max(t, 0), 1) * n;
  const i = Math.min(Math.floor(scaled), n - 1);
  const frac = scaled - i;
  const [r1, g1, b1] = STOPS[i];
  const [r2, g2, b2] = STOPS[i + 1];
  return [
    Math.round(r1 + (r2 - r1) * frac),
    Math.round(g1 + (g2 - g1) * frac),
    Math.round(b1 + (b2 - b1) * frac),
  ];
}
