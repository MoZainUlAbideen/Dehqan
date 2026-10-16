import Link from "next/link";
import PakistanMap from "@/components/PakistanMap";
import { Stat } from "@/components/charts";
import fieldTuned from "@/data/evals/field_tuned.json";
import gate from "@/data/evals/crop_gate.json";
import severity from "@/data/evals/severity.json";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`; // one decimal: never round 99.6 up to 100
const answered = fieldTuned.abstention_field_tuned.curve.find((p) => p.threshold === 0.9)!;

const STEPS = [
  {
    en: { title: "Take a clear photo", body: "One leaf, close up, in daylight and in focus." },
    ur: { title: "صاف تصویر لیں", body: "ایک پتہ قریب سے، دن کی روشنی میں اور واضح لیں۔" },
  },
  {
    en: { title: "Dehqan checks it", body: "Is it a leaf? What might be wrong? How much of the leaf is affected?" },
    ur: { title: "دہقان جانچتا ہے", body: "کیا یہ پتہ ہے؟ کیا مسئلہ ہو سکتا ہے؟ پتے کا کتنا حصہ متاثر ہے؟" },
  },
  {
    en: { title: "Get the answer and safe spray hours", body: "Or an honest “I’m not sure”, and the extension office to ask." },
    ur: { title: "جواب اور سپرے کا محفوظ وقت", body: "یا صاف جواب کہ “مجھے یقین نہیں”، اور رابطے کے لیے زرعی دفتر۔" },
  },
];

export default function Home() {
  return (
    <>
      <section className="hero-glow overflow-hidden border-b border-line">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:py-16">
          <div>
            <p className="font-urdu gradient-text rise text-left text-6xl sm:text-7xl" lang="ur" dir="rtl">
              دہقان
            </p>
            <h1 className="font-display rise rise-2 mt-1 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              A crop doctor that tells you when it is <span className="gradient-text">not sure</span>.
            </h1>
            <p className="rise rise-2 mt-4 max-w-xl text-lg text-ink-2">
              Dehqan looks at a photo of a sick leaf, says what it might be, how bad it is, and when the weather is safe to
              spray. When it is not confident, it says so and sends you to your local agriculture extension office, instead
              of guessing.
            </p>

            {/* Urdu explanation, right on the first screen */}
            <div
              className="rise rise-3 mt-6 max-w-xl rounded-2xl border border-green/40 bg-surface-2/80 p-5 backdrop-blur"
              style={{ boxShadow: "0 14px 40px -18px var(--glow)" }}
              lang="ur"
              dir="rtl"
            >
              <p className="font-urdu text-xl font-semibold text-green">فصل کا ڈاکٹر، جو یقین نہ ہو تو صاف بتا دیتا ہے</p>
              <p className="font-urdu mt-1 text-lg text-ink">
                دہقان آپ کی فصل کی تصویر دیکھ کر بتاتا ہے کہ پودے کو کیا مسئلہ ہو سکتا ہے، بیماری کتنی بڑھ چکی ہے، اور اگلے پانچ
                دنوں میں سپرے کے لیے کون سا وقت محفوظ ہے۔ اگر اسے پوری طرح یقین نہ ہو تو یہ اندازہ لگانے کے بجائے صاف کہہ دیتا ہے
                کہ مجھے یقین نہیں، اور آپ کو اپنے مقامی زرعی توسیعی دفتر سے رجوع کرنے کا مشورہ دیتا ہے۔
              </p>
              <p className="font-urdu mt-1 text-base text-ink-3">
                یہ ابھی ایک تحقیقی نمونہ ہے، زرعی مشورہ نہیں۔ ابھی گندم اور کپاس کی بیماریاں شامل نہیں، اور کیڑے مار ادویات کی
                رہنمائی بھی دستیاب نہیں۔
              </p>
            </div>

            <div className="rise rise-3 mt-7 flex flex-wrap gap-3">
              <Link href="/diagnose" className="btn-primary rounded-xl px-6 py-3 text-center font-semibold">
                Diagnose a leaf
                <span className="font-urdu block text-base leading-snug opacity-90" lang="ur">پتے کی تشخیص</span>
              </Link>
              <Link href="/spray" className="btn-ghost rounded-xl px-6 py-3 text-center font-semibold">
                Find a spray window
                <span className="font-urdu block text-base leading-snug text-ink-2" lang="ur">سپرے کا وقت</span>
              </Link>
            </div>
            <p className="mt-4 text-sm text-ink-3">Research prototype. Not agronomic advice.</p>
          </div>
          <PakistanMap />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <h2 className="font-display text-3xl font-semibold tracking-tight">
          How it works <span className="font-urdu text-2xl text-ink-3" lang="ur" dir="rtl">یہ کیسے کام کرتا ہے</span>
        </h2>
        <ol className="mt-6 grid gap-5 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={i} className="card-lift rounded-2xl border border-line bg-surface-2 p-5">
              <span className="step-num flex h-10 w-10 items-center justify-center rounded-full font-display text-lg font-bold">{i + 1}</span>
              <h3 className="mt-4 font-display text-xl font-semibold">{s.en.title}</h3>
              <p className="mt-1 text-sm text-ink-2">{s.en.body}</p>
              <div className="mt-3 border-t border-line pt-3" lang="ur" dir="rtl">
                <h3 className="font-urdu text-lg font-semibold text-green">{s.ur.title}</h3>
                <p className="font-urdu text-base text-ink-2">{s.ur.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-line bg-surface-2/60">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <h2 className="font-display text-3xl font-semibold tracking-tight">The honest numbers</h2>
          <p className="mt-2 max-w-2xl text-ink-2">
            We measured everything on real field photos, not only clean lab photos, and we publish the bad results too.
          </p>
          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              value={`${pct1(fieldTuned.held_out_field_lab_only_baseline.accuracy)} → ${pct1(fieldTuned.held_out_field_field_tuned.accuracy)}`}
              label="Accuracy on real field photos"
              sub="before and after adding field photos to training. Still not good enough to rely on."
            />
            <Stat
              value={pct(severity.learned_segmentation.grade_accuracy)}
              label="Severity grade right"
              sub={`vs ${pct(severity.naive_mean_baseline.grade_accuracy)} for guessing; weakest on wheat`}
            />
            <Stat
              value={pct1(gate.clip_gate.true_positive_rate)}
              label="Leaf photos accepted"
              sub={`while rejecting ${pct1(1 - gate.clip_gate.false_positive_rate)} of everyday objects; soil and weeds untested`}
            />
            <Stat
              value={pct(answered.coverage)}
              label="Field photos it will answer"
              sub={`at the live confidence setting (0.9), right on ${pct(answered.selective_accuracy)} of those; it defers the rest`}
            />
          </div>
          <p className="mt-6">
            <Link href="/accuracy" className="font-semibold text-green underline underline-offset-4 hover:text-green-bright">
              See how we measured every number →
            </Link>
          </p>
        </div>
      </section>

      <section>
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-2">
          <div>
            <h2 className="font-display text-2xl font-semibold">What works today</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2 marker:text-green">
              <li>Checks that a photo really shows a leaf before diagnosing.</li>
              <li>Names a likely condition from 27 classes across 13 crops, or says it is not sure.</li>
              <li>Estimates how much of the leaf is covered by disease spots.</li>
              <li>Finds low-wind, dry, mild-weather spray windows from a live five-day forecast.</li>
              <li>A safety guardrail that rejects unregistered or banned pesticides and any dose it cannot quote from a source.</li>
              <li>Cotton pesticide options with the dose per acre copied from the official Punjab Agriculture Department bulletin, each with the printed line as proof.</li>
              <li>Satellite field checks, mandi price history, and a question box that answers in English and Urdu.</li>
            </ul>
          </div>
          <div>
            <h2 className="font-display text-2xl font-semibold">Not built yet</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2 marker:text-gold">
              <li>Wheat and cotton diagnosis that works on new cameras. Wheat is trained but only half right on a second source (49% vs a 32% guess), so it is not in the app yet.</li>
              <li>Checking pesticides against the national registered-pesticide list (we could not download it), and protective-gear rules (the bulletin has none). Wheat has no treatment table to copy from.</li>
              <li>Voice notes in Urdu, Pashto and Punjabi, and WhatsApp.</li>
            </ul>
          </div>
        </div>
      </section>
    </>
  );
}
