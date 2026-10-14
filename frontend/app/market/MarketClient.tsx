"use client";

import { useEffect, useState } from "react";
import PriceChart from "@/components/PriceChart";
import { ApiError, marketAnalysis, marketOptions, type MarketAnalysis, type MarketOptions } from "@/lib/api";
import { useSlowHint, WAKING_MESSAGE } from "@/lib/useSlowHint";

type Outcome = { kind: "error"; message: string } | { kind: "ok"; data: MarketAnalysis };
type Settled = { key: string; outcome: Outcome };

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const monthName = (m: string) => `${MONTHS[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}`;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong.");

const SIGNALS = {
  hold: { icon: "▲", title: "Holding may pay", tone: "var(--green)" },
  sell: { icon: "▼", title: "Selling sooner may be better", tone: "var(--gold)" },
  none: { icon: "●", title: "No clear signal", tone: "var(--baseline)" },
} as const;

export default function MarketClient() {
  const [options, setOptions] = useState<MarketOptions | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [commodity, setCommodity] = useState("Wheat");
  const [wantedMarket, setWantedMarket] = useState("Peshawar");
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    marketOptions().then(setOptions).catch((e) => setOptionsError(msg(e)));
  }, []);

  const markets = options?.commodities.find((c) => c.name === commodity)?.markets ?? [];
  const market = markets.includes(wantedMarket) ? wantedMarket : markets[0]; // derived: no setState needed
  const key = `${commodity}|${market}`;

  useEffect(() => {
    if (!options || !market) return;
    let cancelled = false;
    const done = (outcome: Outcome) => !cancelled && setSettled({ key: `${commodity}|${market}`, outcome });
    marketAnalysis(commodity, market)
      .then((data) => done({ kind: "ok", data }))
      .catch((e) => done({ kind: "error", message: msg(e) }));
    return () => {
      cancelled = true;
    };
  }, [options, commodity, market]);

  const state: Outcome | { kind: "loading" } = optionsError
    ? { kind: "error", message: optionsError }
    : settled && settled.key === key
      ? settled.outcome
      : { kind: "loading" };
  const slow = useSlowHint(state.kind === "loading");

  return (
    <div className="mt-8">
      <div className="flex flex-wrap gap-4">
        <label className="text-sm font-medium text-ink-2">
          Crop
          <select value={commodity} onChange={(e) => setCommodity(e.target.value)} className="mt-1 block rounded-lg border border-line bg-surface-2 px-3 py-2 text-ink">
            {(options?.commodities ?? [{ name: "Wheat", unit: "", markets: [] }]).map((c) => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-ink-2">
          Market city
          <select value={market ?? ""} onChange={(e) => setWantedMarket(e.target.value)} className="mt-1 block rounded-lg border border-line bg-surface-2 px-3 py-2 text-ink">
            {markets.map((m) => (<option key={m} value={m}>{m}</option>))}
          </select>
        </label>
      </div>

      <div aria-live="polite" className="mt-6">
        {state.kind === "loading" && <p className="text-ink-3">Loading prices…</p>}
        {slow && <p role="status" className="mt-3 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm">{WAKING_MESSAGE}</p>}
        {state.kind === "error" && <p role="alert" className="rounded-lg border border-bad/40 bg-surface-2 p-4 text-bad">{state.message}</p>}
        {state.kind === "ok" && <Result d={state.data} />}
      </div>
    </div>
  );
}

function Result({ d }: { d: MarketAnalysis }) {
  const s = SIGNALS[d.signal];
  const end = d.forecast[d.forecast.length - 1];
  const change = ((end.price - d.last_price) / d.last_price) * 100;
  const t = d.track_record;
  const narrow = t?.range_actually_contained_outcome != null && t.range_actually_contained_outcome < t.range_target - 0.05;
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <PriceChart data={d} />
      <div className="space-y-5">
        <section className="rounded-2xl border border-line bg-surface-2 p-5" style={{ borderLeft: `6px solid ${s.tone}` }}>
          <h2 className="flex items-center gap-2 font-display text-xl font-semibold">
            <span aria-hidden="true" style={{ color: s.tone }}>{s.icon}</span> {s.title}
          </h2>
          <p className="mt-2 text-ink-2">{d.message}</p>
          <p className="mt-3 text-sm text-ink-3">
            Latest price ({monthName(d.data_as_of)}): <strong className="text-ink">{Math.round(d.last_price)}</strong> {d.unit}. Three months later the
            forecast is {Math.round(end.price)} ({change >= 0 ? "+" : ""}{change.toFixed(1)}%), with a range of {Math.round(end.low)} to {Math.round(end.high)}.
          </p>
        </section>

        <section className="rounded-2xl border border-line bg-surface-2 p-5 text-sm">
          <h2 className="font-display text-lg font-semibold">How good is this forecast?</h2>
          <p className="mt-2 text-ink-2">
            Method used: <strong>{d.method.description}</strong>.{" "}
            {d.method.beats_naive
              ? `In ${d.method.n_past_forecasts} past forecasts its error was ${d.method.past_error_pct}%, against ${d.method.naive_error_pct}% for assuming prices stay the same.`
              : `It was no better than assuming prices stay the same (about ${d.method.naive_error_pct}% error over ${d.method.n_past_forecasts} past forecasts), so that is all it is.`}
          </p>
          {t && t.range_actually_contained_outcome != null && (
            <p className="mt-2 text-ink-2">
              Replaying the last {t.months_checked} months, the range contained what really happened{" "}
              <strong>{Math.round(t.range_actually_contained_outcome * 100)}%</strong> of the time (it aims for {Math.round(t.range_target * 100)}%).
              {narrow && <strong className="text-warn"> For this crop the range has recently been too narrow, so treat it as a minimum.</strong>}
            </p>
          )}
        </section>

        <section className="rounded-2xl border border-gold/50 bg-gold-soft p-5 text-sm">
          <h2 className="font-semibold">Please keep in mind</h2>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2">
            {d.caveats.map((c) => (<li key={c}>{c}</li>))}
          </ul>
          <p className="mt-2 text-xs text-ink-3">Data: {d.source}.</p>
        </section>
      </div>
    </div>
  );
}
