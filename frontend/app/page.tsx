import Link from "next/link";
import PakistanMap from "@/components/PakistanMap";
import { Stat } from "@/components/charts";
import fieldTuned from "@/data/evals/field_tuned.json";
import gate from "@/data/evals/crop_gate.json";
import severity from "@/data/evals/severity.json";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`; // one decimal: never round 99.6 up to 100
const answered = fieldTuned.abstention_field_tuned.curve.find((p) => p.threshold === 0.9)!;

export default function Home() {
  return (
    <>
      <section className="field-texture border-b border-line">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div>
            <p className="font-urdu text-left text-6xl text-green sm:text-7xl" lang="ur" dir="rtl">
              دہقان
            </p>
            <h1 className="font-display mt-2 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              A crop doctor that tells you when it is <span className="text-green">not sure</span>.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink-2">
              Dehqan looks at a photo of a sick leaf, says what it might be, how bad it is, and when the weather is safe to
              spray. When it is not confident, it says so and sends you to your local agriculture extension office, instead
              of guessing.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/diagnose" className="rounded-lg bg-green px-5 py-3 font-semibold text-green-ink">
                Diagnose a leaf
              </Link>
              <Link href="/spray" className="rounded-lg border border-line bg-surface-2 px-5 py-3 font-semibold hover:border-green">
                Find a spray window
              </Link>
            </div>
            <p className="mt-4 text-sm text-ink-3">Research prototype. Not agronomic advice.</p>
          </div>
          <PakistanMap />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
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
          <Stat value={pct(answered.coverage)} label="Field photos it will answer" sub={`at the live confidence setting (0.9), right on ${pct(answered.selective_accuracy)} of those; it defers the rest`} />
        </div>
        <p className="mt-6">
          <Link href="/accuracy" className="font-semibold text-green underline underline-offset-4">
            See how we measured every number →
          </Link>
        </p>
      </section>

      <section className="border-t border-line bg-surface-2">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-2">
          <div>
            <h2 className="font-display text-2xl font-semibold">What works today</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2">
              <li>Checks that a photo really shows a leaf before diagnosing.</li>
              <li>Names a likely condition from 27 classes across 14 crops, or says it is not sure.</li>
              <li>Estimates how much of the leaf is covered by disease spots.</li>
              <li>Finds low-wind, dry, mild-weather spray windows from a live five-day forecast.</li>
              <li>A safety guardrail that rejects unregistered or banned pesticides and any dose it cannot quote from a source.</li>
            </ul>
          </div>
          <div>
            <h2 className="font-display text-2xl font-semibold">Not built yet</h2>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2">
              <li>Wheat and cotton diagnosis that works on new cameras (the crops that matter most here).</li>
              <li>Pesticide advice: it needs the official Pakistani registered-pesticide list and advisories.</li>
              <li>Voice notes in Urdu, Pashto and Punjabi, and WhatsApp.</li>
              <li>Satellite field checks and mandi price advice.</li>
            </ul>
          </div>
        </div>
      </section>
    </>
  );
}
