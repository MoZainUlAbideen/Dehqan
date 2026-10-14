import type { FieldPoint } from "@/lib/api";

// NDVI colours follow the usual convention: dry soil is tan, thin cover is yellow-green, dense crop is deep green.
// Water or shadow (below zero) is blue-grey. Cells with no clear view (cloud) are hatched.
const STOPS: [number, [number, number, number]][] = [
  [0.0, [205, 189, 150]],
  [0.3, [231, 224, 143]],
  [0.55, [143, 207, 106]],
  [0.9, [10, 107, 47]],
];

export function ndviColor(v: number | null): string {
  if (v === null) return "url(#hatch)";
  if (v < 0) return "rgb(138,164,184)";
  const x = Math.min(v, 0.9);
  for (let i = 1; i < STOPS.length; i++) {
    const [a, ca] = STOPS[i - 1];
    const [b, cb] = STOPS[i];
    if (x <= b) {
      const t = (x - a) / (b - a);
      return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * t)).join(",")})`;
    }
  }
  return `rgb(${STOPS[STOPS.length - 1][1].join(",")})`;
}

export function NdviLegend() {
  const steps = [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9];
  return (
    <div className="mt-3 text-xs text-ink-3">
      <div className="flex h-3 w-full max-w-xs overflow-hidden rounded">
        {steps.map((s) => (
          <span key={s} className="flex-1" style={{ background: ndviColor(s) }} />
        ))}
      </div>
      <div className="mt-1 flex max-w-xs justify-between">
        <span>bare soil</span>
        <span>thin cover</span>
        <span>dense crop</span>
      </div>
      <p className="mt-1">Hatched = hidden by cloud or shadow. Blue-grey = water or deep shadow.</p>
    </div>
  );
}

/** The patch as a grid of coloured cells for one date. */
export function NdviGrid({ point, sizeM }: { point: FieldPoint; sizeM: number }) {
  const rows = point.grid.length;
  const cols = point.grid[0]?.length ?? 0;
  const cell = 24;
  return (
    <figure>
      <svg viewBox={`0 0 ${cols * cell} ${rows * cell}`} className="h-auto w-full max-w-md rounded-lg border border-line" role="img" aria-label={`NDVI map of the ${sizeM} metre patch on ${point.date}`}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--surface-3)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--baseline)" strokeWidth="2" />
          </pattern>
        </defs>
        {point.grid.map((row, i) =>
          row.map((v, j) => (
            <rect key={`${i}-${j}`} x={j * cell} y={i * cell} width={cell + 0.5} height={cell + 0.5} fill={ndviColor(v)} style={{ transition: "fill 0.35s ease" }}>
              <title>{v === null ? "hidden by cloud" : `NDVI ${v.toFixed(2)}`}</title>
            </rect>
          )),
        )}
      </svg>
      <figcaption className="mt-1 text-xs text-ink-3">
        About {sizeM} m × {sizeM} m around your pin. North is up. Each square averages a few 10 m satellite pixels.
      </figcaption>
    </figure>
  );
}

const W = 640, H = 260, L = 44, R = 14, T = 14, B = 34;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso: string) => new Date(`${iso}T12:00:00Z`).getTime();

/** Greenness through the year: the median line, the 10th to 90th percentile band, and the selected date. */
export function NdviChart({ points, selected, onSelect }: { points: FieldPoint[]; selected: number; onSelect: (i: number) => void }) {
  const t0 = day(points[0].date), t1 = day(points[points.length - 1].date);
  const x = (iso: string) => L + ((day(iso) - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v: number) => T + (1 - Math.max(0, Math.min(1, v))) * (H - T - B);
  const med = points.map((p) => `${x(p.date).toFixed(1)},${y(p.median ?? 0).toFixed(1)}`);
  const band = [...points.map((p) => `${x(p.date).toFixed(1)},${y(p.p90 ?? 0).toFixed(1)}`), ...[...points].reverse().map((p) => `${x(p.date).toFixed(1)},${y(p.p10 ?? 0).toFixed(1)}`)].join(" ");
  const sel = points[selected];
  const ticks = points.filter((_, i) => i % Math.max(1, Math.ceil(points.length / 6)) === 0);
  const label = (iso: string) => `${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(2, 4)}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Average greenness (NDVI) of the patch through the last year">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
          <text x={L - 8} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--ink-3)">{t.toFixed(2)}</text>
        </g>
      ))}
      {ticks.map((p) => (
        <text key={p.date} x={x(p.date)} y={H - B + 18} fontSize={11} textAnchor="middle" fill="var(--ink-3)">{label(p.date)}</text>
      ))}
      <polygon points={band} fill="var(--green-bright)" opacity={0.2} />
      <polyline points={med.join(" ")} fill="none" stroke="var(--green)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      <line x1={x(sel.date)} x2={x(sel.date)} y1={T} y2={H - B} stroke="var(--gold)" strokeWidth={2} strokeDasharray="4 4" />
      {points.map((p, i) => (
        <g key={p.date} onClick={() => onSelect(i)} className="cursor-pointer">
          <circle cx={x(p.date)} cy={y(p.median ?? 0)} r={14} fill="transparent" />
          <circle cx={x(p.date)} cy={y(p.median ?? 0)} r={i === selected ? 6 : 3.5} fill={i === selected ? "var(--gold-bright)" : "var(--green)"} stroke="var(--surface-2)" strokeWidth={2}>
            <title>{`${p.date}: median NDVI ${p.median?.toFixed(2)}`}</title>
          </circle>
        </g>
      ))}
      <text x={12} y={(T + H - B) / 2} fontSize={12} textAnchor="middle" fill="var(--ink-2)" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>NDVI (greenness)</text>
    </svg>
  );
}
