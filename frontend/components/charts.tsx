// Small, dependency-free charts. Rendered on the server (no client JS).
// Form: "emphasis": the result we want you to read is green, comparisons are muted grey.
// Every chart has direct value labels and a collapsible table with the same numbers.

export type Row = { label: string; value: number; sub?: string; emphasis?: boolean };

export function BarChart({
  title,
  rows,
  unit = "%",
  max = 100,
  caption,
  decimals = 1,
}: {
  title: string;
  rows: Row[];
  unit?: string;
  max?: number;
  caption?: string;
  decimals?: number;
}) {
  const fmt = (v: number) => `${v.toFixed(decimals)}${unit}`;
  return (
    <figure className="rounded-2xl border border-line bg-surface-2 p-5">
      <figcaption className="font-display text-lg font-semibold">{title}</figcaption>
      {caption && <p className="mt-1 text-sm text-ink-2">{caption}</p>}
      <ul className="mt-4 space-y-3">
        {rows.map((r) => (
          <li key={r.label} title={`${r.label}: ${fmt(r.value)}`}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
              <span className={r.emphasis ? "font-semibold text-ink" : "text-ink-2"}>
                {r.label}
                {r.sub && <span className="ml-2 text-xs text-ink-3">{r.sub}</span>}
              </span>
              <span className={`tabular-nums ${r.emphasis ? "font-semibold text-ink" : "text-ink-2"}`}>{fmt(r.value)}</span>
            </div>
            <div className="h-3 w-full rounded-r bg-surface-3" role="img" aria-label={`${r.label}: ${fmt(r.value)}`}>
              <div
                className="h-3 rounded-r"
                style={{ width: `${Math.max(0.5, (r.value / max) * 100)}%`, background: r.emphasis ? "var(--green)" : "var(--baseline)" }}
              />
            </div>
          </li>
        ))}
      </ul>
      <Legend />
      <TableView headers={["Measure", "Value"]} rows={rows.map((r) => [r.label, fmt(r.value)])} />
    </figure>
  );
}

function Legend() {
  return (
    <p className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--green)" }} /> Dehqan model / main result
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--baseline)" }} /> Baseline / comparison
      </span>
    </p>
  );
}

function TableView({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-ink-2 hover:text-green">View as table</summary>
      <table className="mt-2 w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-line text-ink-3">
            {headers.map((h) => (
              <th key={h} className="py-1 pr-3 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line/60">
              {r.map((c, j) => (
                <td key={j} className="py-1 pr-3 tabular-nums">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export type CurvePoint = { threshold: number; coverage: number; accuracy: number | null };

/** Coverage (x) vs accuracy-on-answered (y). One line, a dashed "answer everything" reference. */
export function CoverageChart({
  title,
  caption,
  points,
  answerEverything,
  callouts,
}: {
  title: string;
  caption?: string;
  points: CurvePoint[];
  answerEverything: number; // 0..1
  callouts: number[]; // thresholds to label directly
}) {
  const W = 520, H = 300, L = 48, R = 16, T = 16, B = 44;
  const pts = points.filter((p) => p.accuracy !== null && p.coverage > 0).sort((a, b) => a.coverage - b.coverage);
  const x = (c: number) => L + c * (W - L - R);
  const y = (a: number) => T + (1 - a) * (H - T - B);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(p.coverage).toFixed(1)},${y(p.accuracy as number).toFixed(1)}`).join("");
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const marks = callouts.map((t) => pts.find((p) => Math.abs(p.threshold - t) < 1e-9)).filter(Boolean) as CurvePoint[];
  return (
    <figure className="rounded-2xl border border-line bg-surface-2 p-5">
      <figcaption className="font-display text-lg font-semibold">{title}</figcaption>
      {caption && <p className="mt-1 text-sm text-ink-2">{caption}</p>}
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-auto w-full" role="img" aria-label={title}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={L - 8} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--ink-3)">{Math.round(t * 100)}%</text>
            <text x={x(t)} y={H - B + 18} fontSize={11} textAnchor="middle" fill="var(--ink-3)">{Math.round(t * 100)}%</text>
          </g>
        ))}
        <text x={(L + W - R) / 2} y={H - 6} fontSize={12} textAnchor="middle" fill="var(--ink-2)">Share of photos Dehqan answers (coverage)</text>
        <text x={12} y={(T + H - B) / 2} fontSize={12} textAnchor="middle" fill="var(--ink-2)" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>Accuracy on answered photos</text>
        <line x1={L} x2={W - R} y1={y(answerEverything)} y2={y(answerEverything)} stroke="var(--baseline)" strokeWidth={2} strokeDasharray="6 4" />
        <text x={W - R - 4} y={y(answerEverything) + 16} fontSize={11} textAnchor="end" fill="var(--ink-2)">Answer every photo: {(answerEverything * 100).toFixed(1)}%</text>
        <path d={path} fill="none" stroke="var(--green)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {marks.map((p) => (
          <g key={p.threshold}>
            <circle cx={x(p.coverage)} cy={y(p.accuracy as number)} r={5} fill="var(--green)" stroke="var(--surface-2)" strokeWidth={2} />
            <text x={p.coverage > 0.45 ? x(p.coverage) - 8 : x(p.coverage) + 8} y={y(p.accuracy as number) - 10} textAnchor={p.coverage > 0.45 ? "end" : "start"} fontSize={11} fontWeight={600} fill="var(--ink)" stroke="var(--surface-2)" strokeWidth={3} paintOrder="stroke">
              {`confidence ≥ ${p.threshold}: ${(p.coverage * 100).toFixed(0)}% answered, ${((p.accuracy as number) * 100).toFixed(0)}% right`}
            </text>
          </g>
        ))}
      </svg>
      <TableView
        headers={["Confidence threshold", "Photos answered", "Accuracy on answered"]}
        rows={pts.filter((_, i) => i % 2 === 0).map((p) => [p.threshold, `${(p.coverage * 100).toFixed(1)}%`, `${((p.accuracy as number) * 100).toFixed(1)}%`])}
      />
    </figure>
  );
}

/** One headline number with a short label. */
export function Stat({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-5">
      <p className="font-display text-4xl font-semibold tracking-tight text-green">{value}</p>
      <p className="mt-1 text-sm font-medium text-ink">{label}</p>
      {sub && <p className="mt-1 text-xs text-ink-3">{sub}</p>}
    </div>
  );
}
