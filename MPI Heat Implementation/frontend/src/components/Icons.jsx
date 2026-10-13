// Minimal inline SVG line icons, drawn to match the app's thin-stroke,
// rounded-joint aesthetic. No emoji/dingbat characters anywhere.
const base = {
  width: 17,
  height: 17,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function DashboardIcon(props) {
  return (
    <svg {...base} {...props}>
      <rect x="3.5" y="3.5" width="7.5" height="9" rx="1.6" />
      <rect x="13" y="3.5" width="7.5" height="5.5" rx="1.6" />
      <rect x="13" y="11" width="7.5" height="9.5" rx="1.6" />
      <rect x="3.5" y="14.5" width="7.5" height="6" rx="1.6" />
    </svg>
  );
}

export function BenchmarksIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20V10" />
      <path d="M10.5 20V4" />
      <path d="M17 20v-7" />
      <path d="M2.5 20h19" />
    </svg>
  );
}

export function CorrectnessIcon(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.2 12.3l2.6 2.6 5-5.4" />
    </svg>
  );
}

export function SimulationIcon(props) {
  return (
    <svg {...base} {...props}>
      <rect x="3.2" y="3.2" width="17.6" height="17.6" rx="3" />
      <path d="M10 8.3v7.4l6-3.7z" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ScenariosIcon(props) {
  return (
    <svg {...base} {...props}>
      <rect x="3.3" y="3.3" width="5.4" height="5.4" rx="1" />
      <rect x="9.3" y="3.3" width="5.4" height="5.4" rx="1" />
      <rect x="15.3" y="3.3" width="5.4" height="5.4" rx="1" />
      <rect x="3.3" y="9.3" width="5.4" height="5.4" rx="1" />
      <rect x="9.3" y="9.3" width="5.4" height="5.4" rx="1" />
      <rect x="15.3" y="9.3" width="5.4" height="5.4" rx="1" />
      <rect x="3.3" y="15.3" width="5.4" height="5.4" rx="1" />
      <rect x="9.3" y="15.3" width="5.4" height="5.4" rx="1" />
      <rect x="15.3" y="15.3" width="5.4" height="5.4" rx="1" />
    </svg>
  );
}
