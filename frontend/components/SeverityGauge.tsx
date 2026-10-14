// Semicircle gauge for severity (share of leaf covered by spots).
// Zones match the backend grades: mild < 10%, moderate 10-30%, severe >= 30%.
// The scale tops out at 60% so the useful zones are not squashed; larger values pin to the end.
const MAX = 0.6;
const R = 80;
const CX = 100;
const CY = 100;

const angle = (frac: number) => Math.PI * (1 - Math.min(frac, MAX) / MAX); // pi (left) .. 0 (right)
const pt = (frac: number, r = R): [number, number] => [CX + r * Math.cos(angle(frac)), CY - r * Math.sin(angle(frac))];
const arc = (a: number, b: number) => {
  const [x1, y1] = pt(a);
  const [x2, y2] = pt(b);
  return `M${x1.toFixed(1)},${y1.toFixed(1)} A${R},${R} 0 0 1 ${x2.toFixed(1)},${y2.toFixed(1)}`;
};

const ZONES = [
  { from: 0, to: 0.1, color: "var(--good)", label: "Mild" },
  { from: 0.1, to: 0.3, color: "var(--warn)", label: "Moderate" },
  { from: 0.3, to: MAX, color: "var(--bad)", label: "Severe" },
];

export default function SeverityGauge({ severity, grade }: { severity: number; grade: string }) {
  const [nx, ny] = pt(severity, R - 14);
  const pct = Math.round(severity * 1000) / 10;
  return (
    <figure className="w-full max-w-xs" aria-label={`Severity ${pct} percent of the leaf area, graded ${grade}`}>
      <svg viewBox="0 0 200 120" className="h-auto w-full">
        {ZONES.map((z) => (
          <path key={z.label} d={arc(z.from + 0.002, z.to - 0.002)} stroke={z.color} strokeWidth={14} fill="none" strokeLinecap="butt" />
        ))}
        <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="var(--ink)" strokeWidth={3} strokeLinecap="round" />
        <circle cx={CX} cy={CY} r={6} fill="var(--ink)" />
        <text x={CX - R - 7} y={CY + 16} fontSize={10} fill="var(--ink-3)">0%</text>
        <text x={CX + R - 14} y={CY + 16} fontSize={10} fill="var(--ink-3)">60%+</text>
      </svg>
      <figcaption className="-mt-2 text-center">
        <span className="font-display text-3xl font-semibold">{pct}%</span>
        <span className="ml-2 rounded-full border border-line bg-surface-2 px-3 py-0.5 text-sm font-semibold capitalize">{grade}</span>
        <p className="mt-1 text-xs text-ink-3">of the leaf area is covered by disease spots (rough estimate)</p>
      </figcaption>
    </figure>
  );
}
