"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiError, ask, type AskResult } from "@/lib/api";
import { useSlowHint, WAKING_MESSAGE } from "@/lib/useSlowHint";
import { canListen, canSpeak, listen, speak, stopSpeaking, type VoiceLang } from "@/lib/voice";

const noSubscribe = () => () => {};

const EXAMPLES = [
  { text: "Is it safe to spray tomorrow in Lahore?", ur: false },
  { text: "Should I sell wheat in Multan now?", ur: false },
  { text: "Which pesticide and what dose for rust?", ur: false },
  { text: "My leaves have yellow spots", ur: false },
  { text: "کل لاہور میں سپرے کے لیے موسم کیسا ہے؟", ur: true },
  { text: "گندم کی قیمت پشاور میں کیا ہے؟", ur: true },
];

const SPECIALISTS: Record<string, { label: string; tone: string }> = {
  weather: { label: "Weather agent", tone: "var(--green)" },
  market: { label: "Market agent", tone: "var(--gold)" },
  field: { label: "Satellite field agent", tone: "var(--green)" },
  diagnosis: { label: "Diagnosis (needs a photo)", tone: "var(--gold)" },
  treatment: { label: "Safety: pesticide advice withheld", tone: "var(--bad)" },
  unknown: { label: "Not understood", tone: "var(--baseline)" },
};

type State = { kind: "idle" } | { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; result: AskResult };

export default function AskClient() {
  // A link such as /ask?q=wheat%20price%20in%20Lahore opens with that question already answered.
  const linked = useSearchParams().get("q")?.slice(0, 500) ?? "";
  const [text, setText] = useState(linked);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locError, setLocError] = useState<string | null>(null);
  const [state, setState] = useState<State>(linked ? { kind: "loading" } : { kind: "idle" });
  const [showLang, setShowLang] = useState<"auto" | "en" | "ur">("auto");
  const slow = useSlowHint(state.kind === "loading", 8000);

  // Voice chat: the microphone fills the question, sends it, and the answer is read aloud.
  const micOk = useSyncExternalStore(noSubscribe, canListen, () => false);
  const speakerOk = useSyncExternalStore(noSubscribe, canSpeak, () => false);
  const [voiceLang, setVoiceLang] = useState<VoiceLang>("ur");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceMsg, setVoiceMsg] = useState<string | null>(null);
  const stopListening = useRef<() => void>(() => {});

  function readAloud(r: AskResult, l: VoiceLang = r.language === "ur" ? "ur" : "en") {
    setSpeaking(true);
    const ok = speak(l === "ur" ? r.answer_ur : r.answer_en, l, () => setSpeaking(false));
    if (!ok) {
      setSpeaking(false);
      setVoiceMsg(l === "ur"
        ? "This device has no Urdu voice installed, so the answer cannot be read aloud. Read it on screen, or try your phone."
        : "This device has no English voice to read the answer aloud.");
    }
  }

  function startListening() {
    setVoiceMsg(null);
    stopSpeaking();
    setSpeaking(false);
    setListening(true);
    stopListening.current = listen(
      voiceLang,
      (t) => { setText(t); submit(t, true); },
      (m) => setVoiceMsg(m),
      () => setListening(false),
    );
  }

  // Answers the linked question. State is only set in the request's callbacks, never synchronously in the effect.
  useEffect(() => {
    if (!linked) return;
    let cancelled = false;
    ask(linked)
      .then((result) => !cancelled && setState({ kind: "ok", result }))
      .catch((e) => !cancelled && setState({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." }));
    return () => {
      cancelled = true;
    };
  }, [linked]);

  function submit(q: string, aloud = false) {
    const question = q.trim();
    if (!question) return;
    setState({ kind: "loading" });
    setShowLang("auto");
    ask(question, coords?.lat, coords?.lon)
      .then((result) => { setState({ kind: "ok", result }); if (aloud) readAloud(result, voiceLang); })
      .catch((e) => setState({ kind: "error", message: e instanceof ApiError ? e.message : "Something went wrong." }));
  }

  function useMyLocation() {
    setLocError(null);
    if (!navigator.geolocation) return setLocError("Your browser cannot share its location.");
    navigator.geolocation.getCurrentPosition(
      (p) => setCoords({ lat: Number(p.coords.latitude.toFixed(5)), lon: Number(p.coords.longitude.toFixed(5)) }),
      () => setLocError("Could not get your location. You can write a city name in your question instead."),
      { timeout: 10000 },
    );
  }

  const result = state.kind === "ok" ? state.result : null;
  const lang = result ? (showLang === "auto" ? result.language : showLang) : "en";

  return (
    <div className="mt-8">
      <form onSubmit={(e) => { e.preventDefault(); submit(text); }} className="rounded-2xl border border-line bg-surface-2 p-5">
        <label htmlFor="q" className="block text-sm font-medium text-ink-2">Your question</label>
        <textarea
          id="q" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} rows={3} dir="auto"
          placeholder="e.g. Is it safe to spray tomorrow in Lahore?   یا   گندم کی قیمت کیا ہے؟"
          className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-lg text-ink"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="submit" disabled={state.kind === "loading" || !text.trim()} className="btn-primary rounded-lg px-5 py-2 font-semibold disabled:cursor-not-allowed disabled:opacity-60">
            {state.kind === "loading" ? "Thinking…" : "Ask"}
          </button>
          {micOk ? (
            <span className="flex items-center gap-2">
              <button type="button" onClick={listening ? () => stopListening.current() : startListening} aria-pressed={listening}
                className={`rounded-lg px-4 py-2 text-sm font-semibold ${listening ? "bg-bad text-white" : "btn-ghost"}`}>
                {listening ? "● Listening… (tap to stop)" : "🎤 Speak your question"}
              </button>
              <span className="flex gap-1 text-xs" role="group" aria-label="Voice language">
                {(["ur", "en"] as const).map((l) => (
                  <button key={l} type="button" onClick={() => setVoiceLang(l)} aria-pressed={voiceLang === l}
                    className={`rounded px-2 py-0.5 font-semibold ${voiceLang === l ? "bg-green text-green-ink" : "border border-line text-ink-2"}`}>
                    {l === "en" ? "English" : "اردو"}
                  </button>
                ))}
              </span>
            </span>
          ) : (
            <span className="text-xs text-ink-3">Voice input needs Chrome, Edge or Safari.</span>
          )}
          <button type="button" onClick={useMyLocation} className="btn-ghost rounded-lg px-4 py-2 text-sm font-semibold">
            {coords ? "Location added ✓" : "Use my location"}
          </button>
          {coords && <button type="button" onClick={() => setCoords(null)} className="text-sm text-ink-3 underline">remove</button>}
          <span className="text-xs text-ink-3">{text.length}/500</span>
        </div>
        {locError && <p role="alert" className="mt-2 text-sm text-bad">{locError}</p>}
        {voiceMsg && <p role="alert" className="mt-2 text-sm text-bad">{voiceMsg}</p>}
        <p className="mt-3 text-xs text-ink-3">Voice uses your browser&apos;s built-in speech recognition (the audio goes to the browser maker&apos;s service, not to Dehqan) and a voice installed on your device. Urdu and English only.</p>
        <p className="mt-3 text-xs text-ink-3">Adding your location lets Dehqan answer weather, nearest-market price and satellite questions without you naming a city. It is used for this question only and not stored.</p>
      </form>

      <div className="mt-4">
        <p className="text-sm font-medium text-ink-2">Try an example</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((e) => (
            <li key={e.text}>
              <button type="button" onClick={() => { setText(e.text); submit(e.text); }} lang={e.ur ? "ur" : "en"} dir={e.ur ? "rtl" : "ltr"}
                className={`btn-ghost rounded-full px-4 py-1.5 text-sm ${e.ur ? "font-urdu text-base" : ""}`}>
                {e.text}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div aria-live="polite" className="mt-6">
        {state.kind === "loading" && <p className="text-ink-2">Working out what you need…</p>}
        {slow && <p role="status" className="mt-3 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm">{WAKING_MESSAGE}</p>}
        {state.kind === "error" && <p role="alert" className="rounded-lg border border-bad/40 bg-surface-2 p-4 text-bad">{state.message}</p>}
        {result && (
          <section className="rounded-2xl border border-line bg-surface-2 p-6" style={{ borderLeft: `6px solid ${(SPECIALISTS[result.route] ?? SPECIALISTS.unknown).tone}` }}>
            <div className="flex flex-wrap items-center gap-2">
              {result.routes.map((r) => (
                <span key={r} className="rounded-full border border-line bg-surface px-3 py-0.5 text-xs font-semibold">{(SPECIALISTS[r] ?? SPECIALISTS.unknown).label}</span>
              ))}
              <span className="ml-auto flex gap-1 text-xs" role="group" aria-label="Answer language">
                {(["en", "ur"] as const).map((l) => (
                  <button key={l} type="button" onClick={() => setShowLang(l)} aria-pressed={lang === l}
                    className={`rounded px-2 py-0.5 font-semibold ${lang === l ? "bg-green text-green-ink" : "border border-line text-ink-2"}`}>
                    {l === "en" ? "English" : "اردو"}
                  </button>
                ))}
              </span>
            </div>
            <div className={`mt-4 space-y-3 whitespace-pre-line ${lang === "ur" ? "font-urdu text-xl" : "text-lg"}`} lang={lang} dir={lang === "ur" ? "rtl" : "ltr"}>
              {lang === "ur" ? result.answer_ur : result.answer_en}
            </div>

            {speakerOk && (
              <button type="button" onClick={() => (speaking ? (stopSpeaking(), setSpeaking(false)) : readAloud(result, lang))}
                className="btn-ghost mt-4 rounded-lg px-4 py-2 text-sm font-semibold">
                {speaking ? "■ Stop" : lang === "ur" ? "🔊 جواب سنیں (Listen)" : "🔊 Listen to the answer"}
              </button>
            )}

            {result.needs && <NextStep needs={result.needs} />}

            <p className="mt-4 text-xs text-ink-3">
              Understood: {result.understood.city ? `city ${result.understood.city}` : "no city"} · {result.understood.commodity ? `crop ${result.understood.commodity}` : "no crop"}
              {result.understood.has_coordinates ? " · your location" : ""}
            </p>
            <ul className="mt-1 list-disc pl-5 text-xs text-ink-3">
              {result.limitations.map((l) => (<li key={l}>{l}</li>))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

function NextStep({ needs }: { needs: NonNullable<AskResult["needs"]> }) {
  const box = "mt-4 rounded-lg border border-gold/50 bg-gold-soft p-3 text-sm";
  if (needs === "photo") return <p className={box}>Next step: <Link href="/diagnose" className="font-semibold text-green underline">open the Diagnose page</Link> and send a photo of one leaf.</p>;
  if (needs === "coordinates") return <p className={box}>Next step: <Link href="/field" className="font-semibold text-green underline">open the Field page</Link> and drop your pin, or press &quot;Use my location&quot; above.</p>;
  if (needs === "location") return <p className={box}>Next step: add a city name to your question (for example Lahore, Peshawar or Multan), or press &quot;Use my location&quot; above.</p>;
  if (needs === "commodity") return <p className={box}>Next step: name the crop: wheat, flour (atta), rice, basmati, sugar, masur, moong or mash.</p>;
  return <p className={box}>Next step: say which lentil: masur, moong or mash.</p>;
}
