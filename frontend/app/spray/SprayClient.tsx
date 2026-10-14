"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import PakistanMap from "@/components/PakistanMap";
import SprayTimeline from "@/components/SprayTimeline";
import { ApiError, sprayWindow, type SprayResponse } from "@/lib/api";
import { CITIES, cityById } from "@/lib/cities";

const fmtTime = (iso: string) => iso.slice(11, 16);
const fmtDay = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

type Outcome = { kind: "error"; message: string } | { kind: "ok"; data: SprayResponse };
type Settled = { cityId: string; outcome: Outcome };

export default function SprayClient() {
  const router = useRouter();
  const city = cityById(useSearchParams().get("city")) ?? CITIES[0];
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    let cancelled = false;
    const done = (outcome: Outcome) => !cancelled && setSettled({ cityId: city.id, outcome });
    sprayWindow(city.lat, city.lon)
      .then((data) => done({ kind: "ok", data }))
      .catch((e) => done({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." }));
    return () => {
      cancelled = true;
    };
  }, [city.id, city.lat, city.lon]);

  // Until the result for THIS city arrives, we are loading (derived, so no setState inside the effect).
  const state: Outcome | { kind: "loading" } = settled && settled.cityId === city.id ? settled.outcome : { kind: "loading" };

  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div>
        <label htmlFor="city" className="block text-sm font-medium text-ink-2">Area</label>
        <select
          id="city"
          value={city.id}
          onChange={(e) => router.replace(`/spray?city=${e.target.value}`)}
          className="mt-1 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-ink"
        >
          {CITIES.map((c) => (
            <option key={c.id} value={c.id}>{c.name}: {c.note}</option>
          ))}
        </select>
        <div className="mt-4"><PakistanMap activeId={city.id} /></div>
      </div>

      <div aria-live="polite">
        <h2 className="font-display text-2xl font-semibold">
          {city.name} <span className="font-urdu text-xl text-ink-3" lang="ur" dir="rtl">{city.urdu}</span>
        </h2>
        {state.kind === "loading" && <p className="mt-4 text-ink-3">Reading the forecast…</p>}
        {state.kind === "error" && (
          <p role="alert" className="mt-4 rounded-lg border border-bad/40 bg-surface-2 p-4 text-bad">{state.message}</p>
        )}
        {state.kind === "ok" && (
          <>
            <p className="mt-2 font-medium">{state.data.message}</p>
            {state.data.forecast_start && (
              <div className="mt-5"><SprayTimeline windows={state.data.windows} start={state.data.forecast_start} hours={state.data.forecast_hours} /></div>
            )}
            {state.data.windows.length > 0 && (
              <ul className="mt-6 space-y-2">
                {state.data.windows.map((w) => (
                  <li key={w.start} className="rounded-lg border border-line bg-surface-2 px-4 py-2 text-sm">
                    <span className="font-semibold">{fmtDay(w.start)}</span>, {fmtTime(w.start)} to {fmtTime(w.end)} ({w.hours} h)
                    <span className="ml-2 text-ink-3">wind up to {w.max_wind_kmh} km/h, rain chance up to {w.max_rain_prob_pct}%</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-6 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm text-ink">
              <strong>Note:</strong> {state.data.note}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
