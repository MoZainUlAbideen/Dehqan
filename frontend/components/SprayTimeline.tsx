import type { SprayWindow } from "@/lib/api";

// Day-by-hour grid. A filled cell means the hour is inside a safe spray window.
// Times are local (Asia/Karachi) strings like "2026-10-15T05:00:00"; we never convert time zones.

const pad = (n: number) => String(n).padStart(2, "0");
const dayKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseLocal = (s: string) => {
  const [date, time] = s.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [h] = time.split(":").map(Number);
  return new Date(y, m - 1, d, h);
};
const dayLabel = (d: Date) => d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

export default function SprayTimeline({ windows, start, hours }: { windows: SprayWindow[]; start: string; hours: number }) {
  const first = parseLocal(start);
  const safe = new Set<string>();
  for (const w of windows) {
    const end = parseLocal(w.end);
    for (let t = parseLocal(w.start); t <= end; t = new Date(t.getTime() + 3600_000)) safe.add(`${dayKey(t)}-${t.getHours()}`);
  }
  const days = Math.ceil(hours / 24);
  const rows = Array.from({ length: days }, (_, i) => new Date(first.getFullYear(), first.getMonth(), first.getDate() + i));

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[560px]">
        <div className="ml-24 grid grid-cols-24 text-[10px] text-ink-3" style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}>
          {Array.from({ length: 24 }, (_, h) => (
            <span key={h} className="text-center">
              {h % 3 === 0 ? pad(h) : ""}
            </span>
          ))}
        </div>
        {rows.map((day) => (
          <div key={dayKey(day)} className="mt-1 flex items-center">
            <span className="w-24 shrink-0 pr-2 text-sm text-ink-2">{dayLabel(day)}</span>
            <div className="grid flex-1 gap-[2px]" style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}>
              {Array.from({ length: 24 }, (_, h) => {
                const ok = safe.has(`${dayKey(day)}-${h}`);
                return (
                  <span
                    key={h}
                    title={`${dayLabel(day)} ${pad(h)}:00: ${ok ? "safe to spray" : "not recommended"}`}
                    className="h-6 rounded-[3px]"
                    style={{ background: ok ? "var(--green)" : "var(--surface-3)" }}
                  />
                );
              })}
            </div>
          </div>
        ))}
        <p className="ml-24 mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: "var(--green)" }} /> Safe to spray
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-[3px]" style={{ background: "var(--surface-3)" }} /> Not recommended (wind, rain, heat, night, or unknown)
          </span>
        </p>
      </div>
    </div>
  );
}
