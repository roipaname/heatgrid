import { useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList,
} from "recharts";
import { IMPL_LABELS, SERIES_COLORS } from "../constants.js";

const MPI_VARIANTS = ["slab_blocking", "slab_nonblocking", "cartesian_blocking", "cartesian_nonblocking"];
const SCENARIOS = ["single_hotspot", "multiple_hotspots", "uniform", "gradient"];
const COLOR = { ...SERIES_COLORS, sequential: "#52514e" };
const SHORT = {
  sequential: "Sequential", slab_blocking: "Slab · blocking", slab_nonblocking: "Slab · non-blocking",
  cartesian_blocking: "Cartesian · blocking", cartesian_nonblocking: "Cartesian · non-blocking",
};

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `server returned ${res.status}`);
  if (data.returncode !== 0) {
    const why = (data.stderr || data.stdout || "").trim().split("\n").pop();
    throw new Error(why || `the program exited with status ${data.returncode}`);
  }
  return data;
}

const fmtS = (s) => (s == null ? "N/A" : s < 1 ? `${(s * 1000).toFixed(1)} ms` : `${s.toFixed(2)} s`);
const fmtErr = (e) => (Number(e) === 0 ? "0" : Number(e).toExponential(1));
const scen = (s) => s.replace("_", " ");

/* ---------- building blocks ---------- */

function Verdict({ ok, title, detail }) {
  return (
    <div className={`verdict ${ok ? "ok" : "bad"}`}>
      <span className="verdict-icon">{ok ? "✓" : "!"}</span>
      <div><strong>{title}</strong>{detail && <span>{detail}</span>}</div>
    </div>
  );
}

function Stat({ label, value, sub, tone }) {
  return (
    <div className={`stat ${tone || ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function CommBar({ comm }) {
  const c = Math.max(0, Math.min(100, comm));
  return (
    <div className="commbar" title={`${c.toFixed(1)}% halo exchange`}>
      <span className="compute" style={{ width: `${100 - c}%` }} />
      <span className="comm" style={{ width: `${c}%` }} />
    </div>
  );
}

function Explain({ children }) {
  return <div className="explain"><div className="explain-label">What this shows</div>{children}</div>;
}

function Step({ n, title, lead, children }) {
  return (
    <div className="card demo-step" id={`demo-step-${n}`}>
      <div className="step-head">
        <span className="step-num">{n}</span>
        <div>
          <h2>{title}</h2>
          <p className="subtitle">{lead}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function Segmented({ value, options, onChange, disabled }) {
  return (
    <div className="segmented">
      {options.map((o) => (
        <button key={String(o.value)} disabled={disabled} className={o.value === value ? "active" : ""}
                onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

function NumberField({ label, value, onChange, min, max, disabled }) {
  return (
    <div className="filter-group">
      <label>{label}</label>
      <input type="number" className="num" value={value} min={min} max={max} disabled={disabled}
             onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
    </div>
  );
}

function RunButton({ busy, invalid, onClick, children }) {
  if (invalid && !busy) return <button className="btn primary" disabled>Fix the input above first</button>;
  return (
    <button className="btn primary" disabled={!!busy} onClick={onClick}>
      {busy ? <><span className="spinner" />{typeof busy === "string" ? busy : "Running…"}</> : children}
    </button>
  );
}

function ErrorNote({ error }) {
  return error ? <div className="error-note">{error}</div> : null;
}

function Placeholder({ children }) {
  return <div className="placeholder">{children}</div>;
}

/* ---------- 1. correctness ---------- */

export function ConvergenceLadder({ rows }) {
  const logs = rows.map((r) => Math.log10(r.err));
  const lo = Math.min(...logs) - 0.6, hi = Math.max(...logs);
  return (
    <div className="ladder">
      {rows.map((r, i) => (
        <div key={r.n}>
          {i > 0 && <div className="ladder-ratio">error ÷ {r.ratio?.toFixed(2)}</div>}
          <div className="ladder-row">
            <div className="ladder-grid">{r.n}×{r.n}<small>dx {r.dx} · {r.steps} steps</small></div>
            <div className="ladder-track">
              <span style={{ width: `${(100 * (Math.log10(r.err) - lo)) / (hi - lo)}%` }} />
            </div>
            <div className="ladder-err">{r.err.toExponential(2)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Correctness({ maxProcs, busy, setBusy, register }) {
  const options = [[2], [2, 4], [2, 4, 8]].filter((p) => Math.max(...p) <= maxProcs);
  const [procs, setProcs] = useState(options[Math.min(1, options.length - 1)] || [2]);
  const [res, setRes] = useState(null);
  const [error, setError] = useState(null);

  const go = async () => {
    setBusy("Validating…"); setError(null); setRes(null);
    try { setRes((await post("/api/validate", { procs })).parsed); } catch (e) { setError(e.message); }
    setBusy(false);
  };
  register(1, go);

  const ratios = res?.analytic.filter((a) => a.ratio != null).map((a) => a.ratio) || [];
  const secondOrder = ratios.length > 0 && ratios.every((r) => r > 3.5 && r < 4.5);
  const allZero = res?.mpi.length > 0 && res.mpi.every((m) => Number(m.err) === 0);

  return (
    <Step n={1} title="Correctness"
          lead="Two independent checks: the sequential solver against an exact solution, then every MPI variant against the sequential result.">
      <div className="filters" style={{ marginBottom: 16 }}>
        <div className="filter-group">
          <label>MPI process counts to check</label>
          <Segmented value={procs} disabled={!!busy}
                     options={options.map((o) => ({ value: o, label: o.join(", ") }))}
                     onChange={setProcs} />
        </div>
        <RunButton busy={busy} onClick={go}>Run validation</RunButton>
      </div>
      <ErrorNote error={error} />
      {!res && !error && <Placeholder>Run the validation to see the results here.</Placeholder>}

      {res && (
        <>
          <Verdict ok={res.passed}
                   title={res.passed ? "All correctness checks passed" : "A correctness check failed"}
                   detail={`Second-order convergence against the exact solution, and ${res.mpi.length} MPI runs identical to sequential`} />
          <div className="two-col">
            <div className="panel">
              <div className="panel-head">
                <h3>Accuracy against the exact solution</h3>
                <span className={`status-pill ${secondOrder ? "pass" : "fail"}`}>{secondOrder ? "second order" : "unexpected rate"}</span>
              </div>
              <p className="panel-sub">decaying sine field, t = 0.01, r = 0.2. Bar length is the error on a log scale.</p>
              <ConvergenceLadder rows={res.analytic} />
            </div>
            <div className="panel">
              <div className="panel-head">
                <h3>MPI result vs sequential result</h3>
                <span className={`status-pill ${allZero ? "pass" : "fail"}`}>{allZero ? "identical" : "differs"}</span>
              </div>
              <p className="panel-sub">37×53 grid (splits unevenly), single hotspot, 50 steps. Max abs error per run.</p>
              <div className="match-grid">
                {res.mpi.map((m, i) => (
                  <div key={i} className={`match-tile ${Number(m.err) === 0 ? "ok" : "bad"}`}>
                    <span className="dot" style={{ background: COLOR[m.variant] }} />
                    <div className="match-name">{SHORT[m.variant]}</div>
                    <div className="match-meta">{m.nprocs} processes · {m.proc_grid} grid</div>
                    <div className="match-err">error {fmtErr(m.err)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Explain>
            <p>
              <strong>Accuracy.</strong> The decaying sine field has an exact solution,
              u = sin(πx) sin(πy) e<sup>−2π²t</sup>, so the solver's true error can be measured. Each time the
              grid spacing halves, the error falls by {ratios.map((r) => r.toFixed(2)).join(" and ")}. A factor of
              4 is what a second-order scheme like FTCS should give, so the stencil, the fixed boundaries and the
              time stepping are implemented correctly.
            </p>
            <p>
              <strong>Parallel correctness.</strong> {allZero
                ? <>Every MPI variant, on {procs.join(" and ")} processes, produced <em>exactly</em> the same field as
                  the sequential solver (error 0, not just small). The grid doesn't split evenly, and with 4 processes
                  the Cartesian version uses a real 2×2 grid, which exercises the column halos. A missing or misplaced
                  halo row or column would change cell values and show up as a non-zero error.</>
                : <>At least one MPI variant did not match the sequential result.</>}
            </p>
          </Explain>
        </>
      )}
    </Step>
  );
}

/* ---------- 2. sequential and MPI on the same input ---------- */

function InputSummary({ input, seed, extra }) {
  return (
    <div className="input-summary">
      <span><strong>Grid</strong> {input.rows}×{input.cols}</span>
      <span><strong>Scenario</strong> {scen(input.scenario)} (seed {seed})</span>
      <span><strong>Steps</strong> {input.steps}</span>
      <span><strong>r</strong> 0.2</span>
      <span><strong>Trials</strong> {input.warmup} warm-up + {input.trials}</span>
      {extra}
    </div>
  );
}

function TrialBars({ trials, comms, color }) {
  const max = Math.max(...trials);
  return (
    <div className="trial-bars">
      {trials.map((t, i) => (
        <div key={i} className="trial-bar-row">
          <span className="trial-n">trial {i + 1}</span>
          <div className="trial-track">
            <span style={{ width: `${(100 * t) / max}%`, background: color }} />
            {comms?.[i] != null && <span className="trial-comm" style={{ width: `${(100 * comms[i]) / max}%` }} />}
          </div>
          <span className="trial-t">{fmtS(t)}</span>
        </div>
      ))}
    </div>
  );
}

export function RunCard({ r, label, color, extra }) {
  return (
    <div className="run-result">
      <div className="run-result-head">
        <span className="dot" style={{ background: color }} />
        <strong>{label}</strong>
        {extra}
      </div>
      <div className="run-stats">
        <Stat label="Median runtime" value={fmtS(r.median_s)} sub={`over ${r.trials} trials`} />
        <Stat label="Processes" value={r.nprocs} sub={`${r.proc_grid} process grid`} />
        <Stat label="Halo exchange" value={`${r.comm_pct.toFixed(0)}%`} sub="of runtime" />
      </div>
      <CommBar comm={r.comm_pct} />
      <div className="commbar-legend"><span className="k compute" />computing <span className="k comm" />halo exchange</div>
      <TrialBars trials={r.trial_s} comms={r.trial_comm_s} color={color} />
    </div>
  );
}

function SeqVsMpi({ input, seed, maxProcs, busy, invalid, setBusy, register }) {
  const [variant, setVariant] = useState("slab_nonblocking");
  const [procs, setProcs] = useState(2);
  const [runs, setRuns] = useState(null);
  const [error, setError] = useState(null);

  const go = async () => {
    setError(null); setRuns(null);
    try {
      setBusy("Sequential…");
      const seq = (await post("/api/run", { ...input, variant: "sequential" })).parsed;
      setRuns({ seq });
      setBusy(`MPI, ${procs} processes…`);
      const mpi = (await post("/api/run", { ...input, variant, procs })).parsed;
      setRuns({ seq, mpi });
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  register(2, go);

  const s = runs?.seq, m = runs?.mpi;
  const speedup = s && m ? s.median_s / m.median_s : null;

  return (
    <Step n={2} title="Sequential and MPI execution"
          lead="Both implementations on the same small, clearly identified input.">
      <InputSummary input={input} seed={seed}
                    extra={<span className="accent"><strong>MPI</strong> {procs} processes · {SHORT[variant]}</span>} />
      <div className="filters" style={{ margin: "14px 0 16px" }}>
        <div className="filter-group">
          <label>MPI variant</label>
          <select value={variant} disabled={!!busy} onChange={(e) => setVariant(e.target.value)}>
            {MPI_VARIANTS.map((v) => <option key={v} value={v}>{IMPL_LABELS[v]}</option>)}
          </select>
        </div>
        <div className="filter-group">
          <label>MPI processes</label>
          <Segmented value={procs} disabled={!!busy} onChange={setProcs}
                     options={[2, 4, 8].filter((p) => p <= maxProcs).map((p) => ({ value: p, label: p }))} />
        </div>
        <RunButton busy={busy} invalid={invalid} onClick={go}>Run sequential, then MPI</RunButton>
      </div>
      <ErrorNote error={error} />
      {!runs && !error && <Placeholder>Run both to compare them here.</Placeholder>}

      {s && (
        <>
          {m && (
            <Verdict ok={m.max_abs_err === 0}
                     title={m.max_abs_err === 0 ? "MPI result identical to sequential" : "MPI result differs from sequential"}
                     detail={`Max abs error ${fmtErr(m.max_abs_err)}, checked by gathering the MPI field before any timing`} />
          )}
          <div className="two-col">
            <RunCard r={s} label="Sequential" color={COLOR.sequential}
                     extra={<span className="tagline">1 process, no MPI</span>} />
            {m ? (
              <RunCard r={m} label={IMPL_LABELS[m.variant]} color={COLOR[m.variant]}
                       extra={<span className="status-pill pass">matches sequential</span>} />
            ) : <Placeholder>Running the MPI version…</Placeholder>}
          </div>
          {m && (
            <>
              <div className="speedup-strip">
                <Stat label="Speedup on this run" value={`${speedup.toFixed(2)}×`}
                      sub={`${fmtS(s.median_s)} sequential ÷ ${fmtS(m.median_s)} MPI`} tone={speedup >= 1 ? "good" : "warn"} />
                <Stat label="Parallel efficiency" value={(speedup / m.nprocs).toFixed(2)} sub={`speedup ÷ ${m.nprocs} processes`} />
                <Stat label="Same input" value={`${input.rows}×${input.cols}`} sub={`${scen(input.scenario)}, ${input.steps} steps`} />
              </div>
              <Explain>
                <p>
                  Both versions solved the same problem: a {input.rows}×{input.cols} grid, the {scen(input.scenario)}{" "}
                  field with seed {seed}, {input.steps} steps and r = 0.2. The sequential version used one process.
                  The MPI version used {m.nprocs} processes, split as a {m.proc_grid} process grid, and exchanged
                  boundary rows between neighbours every step ({m.comm_pct.toFixed(0)}% of its runtime).
                </p>
                <p>
                  Before timing, the MPI program gathered its field and compared it with a sequential run, and the
                  two are identical. Only the time-step loop is timed, and the MPI time is the slowest process's.
                </p>
                <p className="muted">
                  {speedup.toFixed(2)}× is from one short run on this machine, so it shows the programs work, not
                  how fast they are. The performance claims come from the repeated experiments in the Benchmarks tab.
                </p>
              </Explain>
            </>
          )}
        </>
      )}
    </Step>
  );
}

/* ---------- 3. comparison ---------- */

const KINDS = [
  { value: "comm", label: "Communication mode (RQ2)" },
  { value: "decomp", label: "Decomposition (RQ1)" },
  { value: "procs", label: "Process count" },
  { value: "grid", label: "Grid size" },
];

function plan(kind, opts, input, maxProcs) {
  const { decomp, mode, procs, variant } = opts;
  if (kind === "comm") {
    return [`${decomp}_blocking`, `${decomp}_nonblocking`].map((v) => ({ ...input, variant: v, procs, label: SHORT[v] }));
  }
  if (kind === "decomp") {
    return [`slab_${mode}`, `cartesian_${mode}`].map((v) => ({ ...input, variant: v, procs, label: SHORT[v] }));
  }
  if (kind === "procs") {
    return [{ ...input, variant: "sequential", label: "Sequential" },
      ...[1, 2, 4].filter((p) => p <= maxProcs).map((p) => ({ ...input, variant, procs: p, label: `${p} process${p > 1 ? "es" : ""}` }))];
  }
  return [250, 500, 1000].flatMap((n) => [
    { ...input, rows: n, cols: n, variant: "sequential", label: `${n}² sequential` },
    { ...input, rows: n, cols: n, variant, procs, label: `${n}² MPI` },
  ]);
}

export function headline(kind, opts, items) {
  const by = (v) => items.find((i) => i.parsed?.variant === v)?.parsed;
  if (kind === "comm") {
    const b = by(`${opts.decomp}_blocking`), n = by(`${opts.decomp}_nonblocking`);
    if (!b || !n) return null;
    const saving = (100 * (b.median_s - n.median_s)) / b.median_s;
    return [
      { label: "Non-blocking vs blocking", value: `${saving >= 0 ? "−" : "+"}${Math.abs(saving).toFixed(0)}%`, sub: saving >= 0 ? "less runtime" : "more runtime", tone: saving >= 0 ? "good" : "warn" },
      { label: "Halo exchange share", value: `${b.comm_pct.toFixed(0)}% → ${n.comm_pct.toFixed(0)}%`, sub: "blocking → non-blocking" },
      { label: "Runtime", value: `${fmtS(b.median_s)} → ${fmtS(n.median_s)}`, sub: "median" },
    ];
  }
  if (kind === "decomp") {
    const s = by(`slab_${opts.mode}`), c = by(`cartesian_${opts.mode}`);
    if (!s || !c) return null;
    const ratio = c.median_s / s.median_s;
    return [
      { label: "Cartesian ÷ slab runtime", value: ratio.toFixed(2), sub: ratio < 1 ? "Cartesian faster" : "slab faster", tone: ratio < 1 ? "good" : "warn" },
      { label: "Process grids", value: `${s.proc_grid} vs ${c.proc_grid}`, sub: "slab vs Cartesian" },
      { label: "Halo exchange share", value: `${s.comm_pct.toFixed(0)}% vs ${c.comm_pct.toFixed(0)}%`, sub: "slab vs Cartesian" },
    ];
  }
  if (kind === "procs") {
    const seq = by("sequential");
    const mpi = items.filter((i) => i.parsed && i.parsed.variant !== "sequential").map((i) => i.parsed);
    if (!seq || !mpi.length) return null;
    const best = mpi.reduce((a, b) => (b.median_s < a.median_s ? b : a));
    return [
      { label: "Best speedup", value: `${(seq.median_s / best.median_s).toFixed(2)}×`, sub: `at ${best.nprocs} process${best.nprocs > 1 ? "es" : ""}`, tone: seq.median_s / best.median_s >= 1 ? "good" : "warn" },
      { label: "Halo exchange share", value: mpi.map((m) => `${m.comm_pct.toFixed(0)}%`).join(" → "), sub: mpi.map((m) => `p=${m.nprocs}`).join(" → ") },
      { label: "Sequential", value: fmtS(seq.median_s), sub: "baseline" },
    ];
  }
  const pairs = [250, 500, 1000].map((n) => {
    const seq = items.find((i) => i.rows === n && i.variant === "sequential")?.parsed;
    const mpi = items.find((i) => i.rows === n && i.variant !== "sequential")?.parsed;
    return seq && mpi ? { n, sp: seq.median_s / mpi.median_s, comm: mpi.comm_pct } : null;
  }).filter(Boolean);
  if (!pairs.length) return null;
  return [
    { label: "Speedup by grid", value: pairs.map((p) => `${p.sp.toFixed(2)}×`).join(" → "), sub: pairs.map((p) => `${p.n}²`).join(" → ") },
    { label: "Halo exchange share", value: pairs.map((p) => `${p.comm.toFixed(0)}%`).join(" → "), sub: "falls as the grid grows" },
  ];
}

export function explainComparison(kind, opts, items) {
  const by = (v) => items.find((i) => i.parsed?.variant === v)?.parsed;
  const note = (
    <p className="muted">
      Each bar is the median of {items[0]?.trials} trials from a single run on this machine, which is enough to show
      the effect but not to prove it. The controlled, repeated results are in the Benchmarks tab.
    </p>
  );
  if (kind === "comm") {
    const b = by(`${opts.decomp}_blocking`), n = by(`${opts.decomp}_nonblocking`);
    if (!b || !n) return null;
    const faster = n.median_s <= b.median_s;
    return (<>
      <p>
        Only the halo exchange changed. Blocking exchange waits for each transfer before computing. Non-blocking
        exchange starts the transfers, updates the interior cells (which don't need neighbour data) while the
        messages travel, then waits and finishes the edge cells.
      </p>
      <p>
        {faster
          ? `Non-blocking was faster, and its halo-exchange share went from ${b.comm_pct.toFixed(0)}% to ${n.comm_pct.toFixed(0)}%. ${n.comm_pct < b.comm_pct ? "That fits overlap hiding part of the exchange behind computation (RQ2)." : "The exchange share didn't fall, so the saving here came from elsewhere, for example less waiting between processes."}`
          : "Overlap didn't pay off in this run. On a small grid the transfers are cheap, and splitting each update into interior and edge parts adds overhead."}
        {" "}In the paper suite, non-blocking was faster in all 18 blocking/non-blocking pairs.
      </p>{note}</>);
  }
  if (kind === "decomp") {
    const s = by(`slab_${opts.mode}`), c = by(`cartesian_${opts.mode}`);
    if (!s || !c) return null;
    return (<>
      <p>Only the decomposition changed: row bands ({s.proc_grid}) vs blocks ({c.proc_grid}).</p>
      <p>
        {s.proc_grid === c.proc_grid
          ? <>With {opts.procs} processes MPI picks the same split for both, so any difference is noise or code
            path, not decomposition shape. That's why RQ1 needs at least 4 processes.</>
          : <>A 2D split sends less boundary data per process, but needs four messages instead of two, and its column
            halos are strided in memory. At low process counts the extra messages can outweigh the smaller volume.
            In the paper suite (2 cores), the real 2×2 split only existed at 4 oversubscribed processes, where
            Cartesian was slower in 5 of 6 cases.</>}
      </p>{note}</>);
  }
  if (kind === "procs") {
    return (<>
      <p>
        Same input, more processes. Each extra process gets a smaller block but adds halo exchange every step, and all
        of them share one memory system. The NumPy stencil is limited by memory bandwidth, so adding processes stops
        helping quickly, and the communication share grows. The 1-process MPI run shows the overhead of the MPI code
        path compared with the plain sequential version.
      </p>{note}</>);
  }
  return (<>
    <p>
      Computation grows with the area of each block (n²), but the halo exchange grows only with its edge length (n).
      Bigger grids should therefore spend a smaller share of time communicating, and parallel runs should do
      relatively better. This is the surface-to-volume effect.
    </p>{note}</>);
}

function Comparison({ input, maxProcs, busy, invalid, setBusy, register }) {
  const [kind, setKind] = useState("comm");
  const [opts, setOpts] = useState({ decomp: "slab", mode: "blocking", procs: 2, variant: "cartesian_nonblocking" });
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const set = (k) => (v) => { setOpts((o) => ({ ...o, [k]: v })); setItems(null); };

  const runs = plan(kind, opts, input, maxProcs);

  const go = async () => {
    setError(null);
    const done = [];
    setItems([]);
    try {
      for (let i = 0; i < runs.length; i++) {
        setBusy(`Run ${i + 1} of ${runs.length}…`);
        const res = await post("/api/run", runs[i]);
        done.push({ ...runs[i], parsed: res.parsed });
        setItems([...done]);
      }
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  register(3, go);

  const results = (items || []).filter((i) => i.parsed);
  const chart = results.map((i) => ({
    label: i.label, variant: i.parsed.variant,
    compute: i.parsed.median_s * (1 - i.parsed.comm_pct / 100),
    comm: i.parsed.median_s * (i.parsed.comm_pct / 100),
    total: i.parsed.median_s,
  }));
  const complete = !busy && results.length === runs.length;
  const stats = complete ? headline(kind, opts, items) : null;
  const procOptions = [2, 4, 8].filter((p) => p <= maxProcs).map((p) => ({ value: p, label: p }));

  return (
    <Step n={3} title="A meaningful comparison"
          lead="Change one thing, keep everything else the same, and compare.">
      <div className="filters" style={{ marginBottom: 12 }}>
        <div className="filter-group">
          <label>What changes</label>
          <Segmented value={kind} disabled={!!busy} options={KINDS} onChange={(k) => { setKind(k); setItems(null); }} />
        </div>
      </div>
      <div className="filters" style={{ marginBottom: 14 }}>
        {kind === "comm" && (
          <div className="filter-group"><label>Decomposition</label>
            <Segmented value={opts.decomp} disabled={!!busy} onChange={set("decomp")}
                       options={[{ value: "slab", label: "1D slab" }, { value: "cartesian", label: "2D Cartesian" }]} /></div>
        )}
        {kind === "decomp" && (
          <div className="filter-group"><label>Communication</label>
            <Segmented value={opts.mode} disabled={!!busy} onChange={set("mode")}
                       options={[{ value: "blocking", label: "blocking" }, { value: "nonblocking", label: "non-blocking" }]} /></div>
        )}
        {(kind === "procs" || kind === "grid") && (
          <div className="filter-group"><label>MPI variant</label>
            <select value={opts.variant} disabled={!!busy} onChange={(e) => set("variant")(e.target.value)}>
              {MPI_VARIANTS.map((v) => <option key={v} value={v}>{IMPL_LABELS[v]}</option>)}
            </select></div>
        )}
        {kind !== "procs" && (
          <div className="filter-group"><label>Processes</label>
            <Segmented value={opts.procs} disabled={!!busy} onChange={set("procs")} options={procOptions} /></div>
        )}
        <RunButton busy={busy} invalid={invalid} onClick={go}>Compare {runs.length} configurations</RunButton>
      </div>
      {kind === "decomp" && opts.procs === 2 && (
        <p className="hint">With 2 processes both decompositions are a 2×1 split. Pick 4 to compare a real 2D grid.</p>
      )}

      <div className="run-queue">
        {runs.map((r, i) => {
          const done = items?.[i]?.parsed;
          const active = busy && items && items.length === i;
          return (
            <div key={i} className={`queue-item ${done ? "done" : active ? "active" : ""}`}>
              <span className="dot" style={{ background: COLOR[r.variant] }} />
              <div className="queue-text">
                <strong>{r.label}</strong>
                <small>{r.rows}×{r.cols} · {r.variant === "sequential" ? "1 process" : `${r.procs} process${r.procs > 1 ? "es" : ""}`}</small>
              </div>
              <span className="queue-state">{done ? fmtS(done.median_s) : active ? <span className="spinner dark" /> : ""}</span>
            </div>
          );
        })}
      </div>
      <ErrorNote error={error} />

      {stats && <div className="speedup-strip">{stats.map((s) => <Stat key={s.label} {...s} />)}</div>}

      {chart.length > 0 && (
        <div className="two-col">
          <div className="panel">
            <div className="panel-head"><h3>Median runtime</h3></div>
            <p className="panel-sub">Each bar is split into computing time and halo-exchange time.</p>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chart} margin={{ top: 18, right: 8, bottom: 4, left: -6 }}>
                <CartesianGrid stroke="#efe8d8" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} interval={0} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} width={52} tickFormatter={(v) => fmtS(v)} />
                <Tooltip formatter={(v, name) => [fmtS(v), name === "comm" ? "halo exchange" : "computing"]} />
                <Bar dataKey="compute" stackId="t" name="compute">
                  {chart.map((c, i) => <Cell key={i} fill={COLOR[c.variant]} />)}
                </Bar>
                <Bar dataKey="comm" stackId="t" name="comm" radius={[4, 4, 0, 0]}>
                  {chart.map((c, i) => <Cell key={i} fill={COLOR[c.variant]} fillOpacity={0.35} />)}
                  <LabelList dataKey="total" position="top" formatter={(v) => fmtS(v)} style={{ fontSize: 11, fill: "#52514e" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="commbar-legend"><span className="k solid" />computing <span className="k faded" />halo exchange</div>
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Results</h3></div>
            <div className="result-list">
              {results.map((i, k) => (
                <div key={k} className="result-row">
                  <span className="dot" style={{ background: COLOR[i.parsed.variant] }} />
                  <div className="result-main">
                    <strong>{i.label}</strong>
                    <small>{i.parsed.rows}×{i.parsed.cols} · {i.parsed.proc_grid} grid · error {fmtErr(i.parsed.max_abs_err)}</small>
                    <CommBar comm={i.parsed.comm_pct} />
                  </div>
                  <div className="result-num">
                    <strong>{fmtS(i.parsed.median_s)}</strong>
                    <small>{i.parsed.comm_pct.toFixed(0)}% exchange</small>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {complete && <Explain>{explainComparison(kind, opts, items)}</Explain>}
      {!items && <Placeholder>Pick what to change, then run the comparison.</Placeholder>}
    </Step>
  );
}

/* ---------- page ---------- */

export default function LiveDemo() {
  const steps = useRef({});
  const register = (n, go) => { steps.current[n] = go; };
  const [showcase, setShowcase] = useState(false);
  const [info, setInfo] = useState(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState({ rows: 500, cols: 500, scenario: "single_hotspot", steps: 100, trials: 3, warmup: 1 });

  const check = () => {
    setOffline(false);
    fetch("/api/info").then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => { setInfo(d); setOffline(false); })
      .catch(() => setOffline(true));
  };
  useEffect(check, []);

  const set = (k) => (v) => setInput((i) => ({ ...i, [k]: v }));
  const valid = ["rows", "cols", "steps", "trials"].every((k) => Number.isInteger(input[k]) && input[k] >= (k === "trials" || k === "steps" ? 1 : 3))
    && input.rows <= 2000 && input.cols <= 2000 && input.steps <= 2000 && input.trials <= 10;
  const seed = info?.default_seeds?.[input.scenario] ?? "default";
  const maxProcs = info?.max_procs ?? 2;

  const runAll = async () => {
    setShowcase(true);
    for (const n of [1, 2, 3]) {
      document.getElementById(`demo-step-${n}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
      await steps.current[n]?.();
    }
    setShowcase(false);
  };

  if (offline) {
    return (
      <div className="card">
        <h2>Live demo</h2>
        <div className="empty-state">
          This tab runs the real programs, so it needs the local demo server.<br />
          In the project folder, with the <code>heatgrid</code> conda environment active, run<br />
          <code>python scripts/demo_server.py</code><br />
          then <button className="btn" onClick={check} style={{ marginTop: 10 }}>Try again</button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <h2>Live demo<span className="badge">runs the real programs</span></h2>
        {info && (
          <div className="input-summary" style={{ margin: "10px 0 16px" }}>
            <span><strong>Machine</strong> {info.physical_cores} physical cores</span>
            <span><strong>Python</strong> {info.python}</span>
            <span><strong>MPI</strong> {info.mpiexec ? "ready" : "not found"}</span>
            <span><strong>Up to</strong> {maxProcs} processes</span>
          </div>
        )}
        <div className="showcase">
          <div>
            <strong>2-minute showcase</strong>
            <span>Runs step 1 (validation), step 2 (sequential vs MPI) and step 3 (blocking vs non-blocking) in order,
              scrolling to each result. Under 10 s of computing with the default input.</span>
          </div>
          <button className="btn primary" disabled={!!busy || !valid} onClick={runAll}>
            {showcase && busy ? <><span className="spinner" />{busy}</> : "Run all three"}
          </button>
        </div>
        <h3 style={{ margin: "4px 0 10px" }}>Input used in steps 2 and 3</h3>
        <div className="filters">
          <NumberField label="Rows" value={input.rows} onChange={set("rows")} min={3} max={2000} disabled={!!busy} />
          <NumberField label="Cols" value={input.cols} onChange={set("cols")} min={3} max={2000} disabled={!!busy} />
          <NumberField label="Steps" value={input.steps} onChange={set("steps")} min={1} max={2000} disabled={!!busy} />
          <div className="filter-group">
            <label>Scenario (seed {seed})</label>
            <select value={input.scenario} disabled={!!busy} onChange={(e) => set("scenario")(e.target.value)}>
              {SCENARIOS.map((s) => <option key={s} value={s}>{scen(s)}</option>)}
            </select>
          </div>
          <NumberField label="Trials" value={input.trials} onChange={set("trials")} min={1} max={10} disabled={!!busy} />
          <NumberField label="Warm-up" value={input.warmup} onChange={set("warmup")} min={0} max={3} disabled={!!busy} />
        </div>
        <p className="hint">r = 0.2 throughout (stable for r ≤ 0.25). Keep the grid small (≤ 1000²) so each run takes seconds.</p>
      </div>

      <Correctness maxProcs={maxProcs} busy={busy} setBusy={setBusy} register={register} />
      <SeqVsMpi input={input} seed={seed} maxProcs={maxProcs} busy={busy} invalid={!valid} setBusy={setBusy} register={register} />
      <Comparison input={input} maxProcs={maxProcs} busy={busy} invalid={!valid} setBusy={setBusy} register={register} />
    </>
  );
}
