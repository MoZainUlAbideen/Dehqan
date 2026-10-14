import type { MarketAnalysis } from "@/lib/api";

// Price history (solid), forecast (dashed) and the range past forecasts have actually landed in (shaded).
// Direct labels at the two points that matter, plus a table with the same numbers.

const W = 640, H = 300, L = 54, R = 16, T = 18, B = 40;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const label = (m: string) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(2, 4)}`;
const r0 = (v: number) => Math.round(v); // whole rupees: more digits would suggest precision the forecast does not have

export default function PriceChart({ data }: { data: MarketAnalysis }) {
  const pts = [...data.history.map((h) => ({ ...h, kind: "h" as const })), ...data.forecast.map((f) => ({ month: f.month, price: f.price, kind: "f" as const }))];
  const lo = Math.min(...data.history.map((h) => h.price), ...data.forecast.map((f) => f.low));
  const hi = Math.max(...data.history.map((h) => h.price), ...data.forecast.map((f) => f.high));
  const pad = (hi - lo) * 0.08 || 1;
  const y0 = Math.max(0, lo - pad), y1 = hi + pad;
  const x = (i: number) => L + (i / (pts.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);

  const nH = data.history.length;
  const line = (arr: { price: number }[], offset: number) => arr.map((p, i) => `${i ? "L" : "M"}${x(i + offset).toFixed(1)},${y(p.price).toFixed(1)}`).join("");
  const histPath = line(data.history, 0);
  const fcPoints = [{ price: data.last_price }, ...data.forecast];
  const fcPath = fcPoints.map((p, i) => `${i ? "L" : "M"}${x(nH - 1 + i).toFixed(1)},${y(p.price).toFixed(1)}`).join("");
  const band =
    `M${x(nH - 1).toFixed(1)},${y(data.last_price).toFixed(1)}` +
    data.forecast.map((f, i) => `L${x(nH + i).toFixed(1)},${y(f.high).toFixed(1)}`).join("") +
    [...data.forecast].reverse().map((f, i) => `L${x(nH + data.forecast.length - 1 - i).toFixed(1)},${y(f.low).toFixed(1)}`).join("") + "Z";

  const yTicks = Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4);
  const xTicks = pts.map((p, i) => ({ p, i })).filter(({ i }) => (i % 6 === 0 && i < pts.length - 4) || i === pts.length - 1);
  const end = data.forecast[data.forecast.length - 1];
  const unit = data.unit.replace("PKR per ", "");

  return (
    <figure className="rounded-2xl border border-line bg-surface-2 p-5">
      <figcaption className="font-display text-lg font-semibold">
        {data.commodity} in {data.market}: price history and a three-month look ahead
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-auto w-full" role="img" aria-label={`${data.commodity} price in ${data.market}, ${data.unit}`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={L - 8} y={y(t) + 4} fontSize={11} textAnchor="end" fill="var(--ink-3)">{Math.round(t)}</text>
          </g>
        ))}
        {xTicks.map(({ p, i }) => (
          <text key={p.month} x={x(i)} y={H - B + 18} fontSize={11} textAnchor="middle" fill="var(--ink-3)">{label(p.month)}</text>
        ))}
        <text x={12} y={(T + H - B) / 2} fontSize={12} textAnchor="middle" fill="var(--ink-2)" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>PKR per {unit}</text>
        <path d={band} fill="var(--gold-bright)" opacity={0.28} />
        <line x1={x(nH - 1)} x2={x(nH - 1)} y1={T} y2={H - B} stroke="var(--baseline)" strokeWidth={1} strokeDasharray="3 4" />
        <path d={histPath} fill="none" stroke="var(--green)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        <path d={fcPath} fill="none" stroke="var(--gold)" strokeWidth={2.5} strokeDasharray="6 5" strokeLinecap="round" />
        <circle cx={x(nH - 1)} cy={y(data.last_price)} r={5} fill="var(--green)" stroke="var(--surface-2)" strokeWidth={2} />
        <text x={x(nH - 1) - 8} y={y(data.last_price) - 12} fontSize={12} fontWeight={600} textAnchor="end" fill="var(--ink)" stroke="var(--surface-2)" strokeWidth={3} paintOrder="stroke">
          Latest ({label(data.data_as_of)}): {r0(data.last_price)}
        </text>
        <text x={W - R} y={Math.max(T + 12, y(end.high) - 8)} fontSize={12} fontWeight={600} textAnchor="end" fill="var(--ink)" stroke="var(--surface-2)" strokeWidth={3} paintOrder="stroke">
          {label(end.month)}: {r0(end.price)} (range {r0(end.low)}–{r0(end.high)})
        </text>
      </svg>
      <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
        <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5" style={{ background: "var(--green)" }} /> Actual retail price</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5" style={{ background: "var(--gold)" }} /> Forecast</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-5 rounded-sm opacity-60" style={{ background: "var(--gold-bright)" }} /> Range past forecasts of this kind landed in (10th to 90th percentile)</span>
      </p>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-ink-2 hover:text-green">View as table</summary>
        <table className="mt-2 w-full border-collapse text-left">
          <thead><tr className="border-b border-line text-ink-3"><th className="py-1 pr-3 font-medium">Month</th><th className="py-1 pr-3 font-medium">Price</th><th className="py-1 font-medium">Range</th></tr></thead>
          <tbody>
            {data.history.slice(-6).map((h) => (<tr key={h.month} className="border-b border-line/60"><td className="py-1 pr-3">{label(h.month)}</td><td className="py-1 pr-3 tabular-nums">{r0(h.price)}</td><td className="py-1 text-ink-3">actual</td></tr>))}
            {data.forecast.map((f) => (<tr key={f.month} className="border-b border-line/60"><td className="py-1 pr-3">{label(f.month)}</td><td className="py-1 pr-3 tabular-nums">{r0(f.price)}</td><td className="py-1 tabular-nums">{r0(f.low)} to {r0(f.high)}</td></tr>))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
