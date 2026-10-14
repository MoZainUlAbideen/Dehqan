"use client";

import { useEffect, useRef, useState } from "react";
import SeverityGauge from "@/components/SeverityGauge";
import { ApiError, diagnose, type DiagnosisResult } from "@/lib/api";
import { prettyLabel } from "@/lib/labels";
import { useSlowHint, WAKING_MESSAGE } from "@/lib/useSlowHint";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "done"; result: DiagnosisResult };

const MAX_MB = 5;

export default function DiagnoseClient() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [state, setState] = useState<State>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const slow = useSlowHint(state.kind === "loading");

  const previewRef = useRef<string | null>(null);
  useEffect(() => () => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
  }, []);

  function pick(f: File | undefined) {
    if (!f) return;
    setState({ kind: "idle" });
    if (!f.type.startsWith("image/")) return setState({ kind: "error", message: "Please choose a photo (JPEG, PNG or WebP)." });
    if (f.size > MAX_MB * 1024 * 1024) return setState({ kind: "error", message: `That photo is larger than ${MAX_MB} MB. Try a smaller one.` });
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = URL.createObjectURL(f);
    setPreview(previewRef.current);
    setFile(f);
  }

  async function run() {
    if (!file) return;
    setState({ kind: "loading" });
    try {
      setState({ kind: "done", result: await diagnose(file) });
    } catch (e) {
      setState({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong. Please try again." });
    }
  }

  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-2">
      <div>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            pick(e.dataTransfer.files[0]);
          }}
          className={`flex min-h-72 flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-colors ${
            dragging ? "border-gold bg-gold-soft" : "border-line bg-surface-2"
          }`}
        >
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="The leaf photo you selected" className="max-h-80 rounded-lg object-contain" />
          ) : (
            <>
              <p className="font-display text-xl font-semibold">Drop a leaf photo here</p>
              <p className="mt-1 text-sm text-ink-3">or use the buttons below. JPEG, PNG or WebP, up to {MAX_MB} MB.</p>
            </>
          )}
        </div>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          className="sr-only"
          onChange={(e) => pick(e.target.files?.[0])}
          aria-label="Choose or take a leaf photo"
        />
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => input.current?.click()}
            className="rounded-lg border border-line bg-surface-2 px-4 py-2 font-medium hover:border-green"
          >
            {file ? "Choose a different photo" : "Choose or take a photo"}
          </button>
          <button
            type="button"
            onClick={run}
            disabled={!file || state.kind === "loading"}
            className="btn-primary rounded-lg px-5 py-2 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            {state.kind === "loading" ? "Looking at your leaf…" : "Diagnose"}
          </button>
        </div>
        {slow && <p role="status" className="mt-3 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm">{WAKING_MESSAGE}</p>}
        <p className="mt-3 text-xs text-ink-3">Your photo is sent to the Dehqan server for analysis and is not stored.</p>
      </div>

      <div aria-live="polite">
        {state.kind === "idle" && !file && <Placeholder />}
        {state.kind === "error" && (
          <p role="alert" className="rounded-2xl border border-bad/40 bg-surface-2 p-5 text-bad">{state.message}</p>
        )}
        {state.kind === "done" && <Result r={state.result} />}
      </div>
    </div>
  );
}

function Placeholder() {
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-6 text-sm text-ink-2">
      <p className="font-display text-lg font-semibold text-ink">What to expect</p>
      <ul className="mt-3 list-disc space-y-2 pl-5">
        <li>One leaf, in focus, in daylight, filling most of the photo.</li>
        <li>If it is not a leaf, Dehqan will ask for a better photo.</li>
        <li>If Dehqan is unsure, it says so and sends you to the extension office.</li>
        <li>Right now it knows 27 conditions across 14 crops. <strong>Wheat and cotton are not covered yet.</strong></li>
      </ul>
    </div>
  );
}

function Result({ r }: { r: DiagnosisResult }) {
  if (r.status === "not_a_crop") {
    return (
      <Card tone="neutral" title="That does not look like a leaf">
        <p>{r.message}</p>
      </Card>
    );
  }
  if (r.status === "uncertain") {
    return (
      <Card tone="warn" title="I'm not sure">
        <p>{r.message}</p>
        {r.confidence !== null && (
          <p className="mt-2 text-sm text-ink-3">Confidence was only {(r.confidence * 100).toFixed(0)}%, below the level at which Dehqan is willing to answer.</p>
        )}
        <Limitations items={r.limitations} />
      </Card>
    );
  }
  const { crop, condition } = prettyLabel(r.label ?? "");
  return (
    <Card tone={r.is_healthy ? "good" : "warn"} title={r.is_healthy ? "Looks healthy" : "Possible diagnosis"}>
      <p className="font-display text-3xl font-semibold">
        {crop}
        {condition && <span className="text-ink-2">: {condition}</span>}
      </p>
      {r.confidence !== null && <p className="mt-1 text-sm text-ink-3">Model confidence {(r.confidence * 100).toFixed(0)}%</p>}
      {r.severity !== null && r.severity_grade && (
        <div className="mt-5"><SeverityGauge severity={r.severity} grade={r.severity_grade} /></div>
      )}
      <p className="mt-4">{r.message}</p>
      <Limitations items={r.limitations} />
    </Card>
  );
}

const TONES = { neutral: "var(--baseline)", warn: "var(--gold)", good: "var(--green)" } as const;

function Card({ tone, title, children }: { tone: keyof typeof TONES; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface-2 p-6" style={{ borderLeft: `6px solid ${TONES[tone]}` }}>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-3">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Limitations({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-5 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm">
      <p className="font-semibold">Please keep in mind</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-2">
        {items.map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
