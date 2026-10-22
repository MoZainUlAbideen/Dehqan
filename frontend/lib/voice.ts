// Browser voice for Dehqan: speech in (Web Speech API) and speech out (speechSynthesis).
//
// Free and runs in the farmer's browser, so it costs the server nothing. Two honest limits:
//  - Speech-to-text is built into Chrome/Edge/Safari and sends the audio to the browser maker's service. Firefox has none.
//  - Text-to-speech needs an Urdu voice installed on the device. Android and many Windows PCs have one; some do not.
// Pashto and Punjabi are not supported by these browser services, so they are not offered.

export type VoiceLang = "ur" | "en";

export const RECOGNITION_LANG: Record<VoiceLang, string> = { ur: "ur-PK", en: "en-PK" };

type RecognitionEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
};
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const canListen = () => recognitionCtor() !== null;
export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;

const ERRORS: Record<string, string> = {
  "not-allowed": "The microphone is blocked. Allow it in your browser's address bar and try again.",
  "service-not-allowed": "The microphone is blocked. Allow it in your browser's address bar and try again.",
  "no-speech": "I did not hear anything. Press the microphone and speak again.",
  "audio-capture": "No microphone was found.",
  network: "Speech recognition needs an internet connection.",
  "language-not-supported": "This browser cannot recognise that language.",
};

/** Listen once. Calls onText with the final transcript; onError with a plain-language message. Returns a stop function. */
export function listen(lang: VoiceLang, onText: (t: string) => void, onError: (m: string) => void, onEnd: () => void): () => void {
  const Ctor = recognitionCtor();
  if (!Ctor) {
    onError("This browser cannot listen. Try Chrome, Edge or Safari, or type your question.");
    onEnd();
    return () => {};
  }
  const rec = new Ctor();
  rec.lang = RECOGNITION_LANG[lang];
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  let heard = false;
  rec.onresult = (e) => {
    const t = e.results[0]?.[0]?.transcript?.trim();
    if (t) {
      heard = true;
      onText(t);
    }
  };
  rec.onerror = (e) => onError(ERRORS[e.error] ?? `Speech recognition failed (${e.error}).`);
  rec.onend = () => {
    if (!heard) onError(ERRORS["no-speech"]);
    onEnd();
  };
  try {
    rec.start();
  } catch {
    onError("Could not start the microphone.");
    onEnd();
  }
  return () => rec.stop();
}

/** The first installed voice for a language (e.g. "ur"), or null. Voices load late in some browsers. */
export function findVoice(lang: VoiceLang): SpeechSynthesisVoice | null {
  if (!canSpeak()) return null;
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang.toLowerCase().startsWith(lang)) ?? null;
}

/** Speak text aloud. Returns false (and says nothing) if the device has no voice for the language. */
export function speak(text: string, lang: VoiceLang, onDone: () => void = () => {}): boolean {
  if (!canSpeak()) return false;
  const voice = findVoice(lang);
  if (!voice) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.voice = voice;
  u.lang = voice.lang;
  u.rate = 0.95;
  u.onend = onDone;
  u.onerror = onDone;
  window.speechSynthesis.speak(u);
  return true;
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel();
}
