"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { NdviChart, NdviGrid, NdviLegend } from "@/components/NdviViews";
import { ApiError, fieldNdvi, type FieldReport } from "@/lib/api";
import { useSlowHint, WAKING_MESSAGE } from "@/lib/useSlowHint";

// Example spots picked because they are farmland (checked on satellite data); not anyone's registered field.
const EXAMPLES = [
  { id: "charsadda", label: "Wheat valley near Charsadda (KP)", lat: 34.13, lon: 71.75 },
  { id: "jhang", label: "Farmland near Jhang (Punjab)", lat: 31.3, lon: 72.9 },
  { id: "multan", label: "Farmland near Multan (Punjab)", lat: 30.05, lon: 71.3 },
];

type State = { kind: "idle" } | { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; report: FieldReport };

const fmtDate = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export default function FieldClient() {
  // A shareable link such as /field?spot=jhang&run=1 opens an example spot and checks it straight away.
  const params = useSearchParams();
  const linked = EXAMPLES.find((e) => e.id === params.get("spot"));
  const autoRun = Boolean(linked) && params.get("run") === "1";
  const [exampleId, setExampleId] = useState(linked?.id ?? "charsadda");
  const [custom, setCustom] = useState(false);
  const [lat, setLat] = useState(String(linked?.lat ?? 34.13));
  const [lon, setLon] = useState(String(linked?.lon ?? 71.75));
  const [size, setSize] = useState(300);
  const [state, setState] = useState<State>(autoRun ? { kind: "loading" } : { kind: "idle" });
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [locError, setLocError] = useState<string | null>(null);
  const latest = useRef(0);
  const slow = useSlowHint(state.kind === "loading", 8000);

  const points = state.kind === "ok" ? state.report.points : [];

  // Starts the linked check. State is only set in the request's callbacks, never synchronously in the effect.
  useEffect(() => {
    if (!autoRun || !linked) return;
    let cancelled = false;
    fieldNdvi(linked.lat, linked.lon, 300)
      .then((report) => {
        if (cancelled) return;
        setSelected(Math.max(0, report.points.length - 1));
        setState({ kind: "ok", report });
      })
      .catch((e) => !cancelled && setState({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." }));
    return () => {
      cancelled = true;
    };
  }, [autoRun, linked]);

  // Play: step through the dates, then stop on the last one.
  useEffect(() => {
    if (!playing || points.length < 2) return;
    const timer = setInterval(() => {
      setSelected((s) => {
        if (s >= points.length - 1) {
          setPlaying(false);
          return s;
        }
        return s + 1;
      });
    }, 650);
    return () => clearInterval(timer);
  }, [playing, points.length]);

  function pickExample(id: string) {
    const e = EXAMPLES.find((x) => x.id === id)!;
    setExampleId(id);
    setCustom(false);
    setLat(String(e.lat));
    setLon(String(e.lon));
  }

  function useMyLocation() {
    setLocError(null);
    if (!navigator.geolocation) return setLocError("Your browser cannot share its location.");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCustom(true);
        setLat(pos.coords.latitude.toFixed(5));
        setLon(pos.coords.longitude.toFixed(5));
      },
      () => setLocError("Could not get your location. You can type the coordinates instead."),
      { timeout: 10000 },
    );
  }

  function run() {
    const la = Number(lat), lo = Number(lon);
    if (!Number.isFinite(la) || !Number.isFinite(lo)) return setState({ kind: "error", message: "Please enter the latitude and longitude as numbers." });
    startRun(la, lo, size);
  }

  function startRun(la: number, lo: number, sizeM: number) {
    const id = ++latest.current;
    setPlaying(false);
    setState({ kind: "loading" });
    fieldNdvi(la, lo, sizeM)
      .then((report) => {
        if (id !== latest.current) return;
        setSelected(Math.max(0, report.points.length - 1));
        setState({ kind: "ok", report });
      })
      .catch((e) => id === latest.current && setState({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." }));
  }

  const report = state.kind === "ok" ? state.report : null;
  const point = report && report.points.length ? report.points[Math.min(selected, report.points.length - 1)] : null;

  return (
    <div className="mt-8">
      <div className="rounded-2xl border border-line bg-surface-2 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm font-medium text-ink-2">
            Example spot
            <select value={custom ? "custom" : exampleId} onChange={(e) => (e.target.value === "custom" ? setCustom(true) : pickExample(e.target.value))} className="mt-1 block rounded-lg border border-line bg-surface px-3 py-2 text-ink">
              {EXAMPLES.map((e) => (<option key={e.id} value={e.id}>{e.label}</option>))}
              <option value="custom">My own pin…</option>
            </select>
          </label>
          <label className="text-sm font-medium text-ink-2">
            Latitude
            <input value={lat} onChange={(e) => { setLat(e.target.value); setCustom(true); }} inputMode="decimal" className="mt-1 block w-32 rounded-lg border border-line bg-surface px-3 py-2 text-ink" />
          </label>
          <label className="text-sm font-medium text-ink-2">
            Longitude
            <input value={lon} onChange={(e) => { setLon(e.target.value); setCustom(true); }} inputMode="decimal" className="mt-1 block w-32 rounded-lg border border-line bg-surface px-3 py-2 text-ink" />
          </label>
          <label className="text-sm font-medium text-ink-2">
            Patch size
            <select value={size} onChange={(e) => setSize(Number(e.target.value))} className="mt-1 block rounded-lg border border-line bg-surface px-3 py-2 text-ink">
              <option value={200}>200 m</option>
              <option value={300}>300 m</option>
              <option value={500}>500 m</option>
            </select>
          </label>
          <button type="button" onClick={useMyLocation} className="btn-ghost rounded-lg px-4 py-2 text-sm font-semibold">Use my location</button>
          <button type="button" onClick={run} disabled={state.kind === "loading"} className="btn-primary rounded-lg px-5 py-2 font-semibold disabled:cursor-not-allowed disabled:opacity-60">
            {state.kind === "loading" ? "Reading satellite pictures…" : "Check this field"}
          </button>
        </div>
        {locError && <p role="alert" className="mt-2 text-sm text-bad">{locError}</p>}
        <p className="mt-3 text-xs text-ink-3">Examples are farmland spots used for demonstration, not anyone&apos;s registered field. Pakistan only. Your coordinates are used for this request and not stored.</p>
      </div>

      <div aria-live="polite" className="mt-6">
        {state.kind === "loading" && (
          <p className="text-ink-2">Reading about two dozen satellite pictures of this spot. This can take up to a minute…</p>
        )}
        {slow && <p role="status" className="mt-3 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm">{WAKING_MESSAGE}</p>}
        {state.kind === "error" && <p role="alert" className="rounded-lg border border-bad/40 bg-surface-2 p-4 text-bad">{state.message}</p>}
        {report && !point && <p className="rounded-lg border border-gold/50 bg-gold-soft p-4">{report.message}</p>}
        {report && point && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <section className="rounded-2xl border border-line bg-surface-2 p-5">
              <h2 className="font-display text-xl font-semibold">{fmtDate(point.date)}</h2>
              <div className="mt-3"><NdviGrid point={point} sizeM={report.size_m} /></div>
              <NdviLegend />
              <div className="mt-4 flex items-center gap-3">
                <button type="button" onClick={() => { if (selected >= report.points.length - 1) setSelected(0); setPlaying((p) => !p); }} className="btn-primary rounded-lg px-4 py-2 text-sm font-semibold" aria-pressed={playing}>
                  {playing ? "❚❚ Pause" : "▶ Play the year"}
                </button>
                <input type="range" min={0} max={report.points.length - 1} value={Math.min(selected, report.points.length - 1)} onChange={(e) => { setPlaying(false); setSelected(Number(e.target.value)); }} className="h-2 flex-1 cursor-pointer accent-[var(--green)]" aria-label="Choose a date" aria-valuetext={fmtDate(point.date)} />
              </div>
              <p className="mt-4 text-sm text-ink-2">
                <strong className="text-ink">Median NDVI {point.median?.toFixed(2)}</strong> · {Math.round(point.valid_fraction * 100)}% of the patch clear on this day
              </p>
              <p className="mt-2 rounded-lg border border-line bg-surface p-3 text-sm text-ink-2">{point.assessment.message}</p>
            </section>

            <div className="space-y-5">
              <section className="rounded-2xl border border-line bg-surface-2 p-5">
                <h2 className="font-display text-lg font-semibold">Greenness through the year</h2>
                <NdviChart points={report.points} selected={Math.min(selected, report.points.length - 1)} onSelect={(i) => { setPlaying(false); setSelected(i); }} />
                <p className="mt-1 text-xs text-ink-3">Line = middle value of the patch; band = the greenest and least green 10% of it. Click a point to jump to that date.</p>
              </section>

              <section className="rounded-2xl border border-line bg-surface-2 p-5 text-sm">
                <h2 className="font-display text-lg font-semibold">Latest view and last year</h2>
                <p className="mt-2 text-ink-2">{report.message}</p>
                {report.last_year ? (
                  <p className="mt-2 text-ink-2">
                    Compared with the same time last year ({report.last_year.last_year_date ? fmtDate(report.last_year.last_year_date) : "a year ago"}), greenness is{" "}
                    <strong>{Math.abs(report.last_year.change_pct)}% {report.last_year.change_pct < 0 ? "lower" : "higher"}</strong> ({report.last_year.now.toFixed(2)} vs {report.last_year.last_year.toFixed(2)}).
                    Sowing dates and rain differ each year, so a difference is a reason to look, not a verdict.
                  </p>
                ) : (
                  <p className="mt-2 text-ink-3">No comparable clear picture from a year ago, or the ground was bare then.</p>
                )}
                <p className="mt-3 text-xs text-ink-3">
                  Used {report.scenes_used} clear dates from the last 12 months{report.scenes_timed_out > 0 ? ` (${report.scenes_timed_out} pictures were not read in time, so some dates are missing)` : ""}. Took {report.seconds} s.
                </p>
              </section>

              <section className="rounded-2xl border border-gold/50 bg-gold-soft p-5 text-sm">
                <h2 className="font-semibold">Please keep in mind</h2>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2">
                  {report.caveats.map((c) => (<li key={c}>{c}</li>))}
                </ul>
                <p className="mt-2 text-xs text-ink-3">Data: {report.source}.</p>
              </section>
            </div>
          </div>
        )}
        {state.kind === "idle" && (
          <p className="rounded-2xl border border-line bg-surface-2 p-5 text-sm text-ink-2">
            Pick an example spot (or enter your own coordinates) and press <strong>Check this field</strong>. The first check of a place takes up to a minute; repeat checks are instant.
          </p>
        )}
      </div>
    </div>
  );
}
