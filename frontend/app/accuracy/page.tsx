import { BarChart, CoverageChart, Stat, type CurvePoint } from "@/components/charts";
import cotton from "@/data/evals/cotton_cross_source.json";
import corn from "@/data/evals/corn_field.json";
import gate from "@/data/evals/crop_gate.json";
import fieldTuned from "@/data/evals/field_tuned.json";
import market from "@/data/evals/market_forecast.json";
import router from "@/data/evals/router.json";
import baseline from "@/data/evals/baseline_lab_vs_field.json";
import severity from "@/data/evals/severity.json";

export const metadata = { title: "How we measured accuracy | Dehqan" };

const pct = (v: number) => v * 100;

export default function AccuracyPage() {
  const labOnlyField = fieldTuned.held_out_field_lab_only_baseline;
  const tunedField = fieldTuned.held_out_field_field_tuned;
  const curve: CurvePoint[] = fieldTuned.abstention_field_tuned.curve.map((p) => ({
    threshold: p.threshold,
    coverage: p.coverage,
    accuracy: p.selective_accuracy,
  }));
  const corn72 = corn.models.field_tuned;
  const cornLab = corn.models.lab_only_baseline;
  const sev = severity;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">How we measured accuracy</h1>
      <p className="mt-3 max-w-3xl text-lg text-ink-2">
        Most crop-disease demos show one big number measured on tidy lab photos. We show what happens on real field photos,
        including the bad numbers, and compare every result with a simple baseline. Everything on this page is read directly
        from the evaluation files in the project repository.
      </p>

      <section className="mt-10">
        <h2 className="font-display text-2xl font-semibold">1. The lab-to-field gap</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          A model trained on clean lab photos (PlantVillage) scores {pct(baseline.lab_test.accuracy).toFixed(1)}% on more lab
          photos, and then collapses on photos taken in real fields (PlantDoc). Adding about 1,800 field photos to
          training helps a lot, but it is still not good enough to give advice.
        </p>
        <div className="mt-5 grid gap-5 md:grid-cols-3">
          <Stat value={`${pct(baseline.lab_test.accuracy).toFixed(1)}%`} label="Lab photos, lab-trained model" sub="the number demos usually show" />
          <Stat value={`${pct(labOnlyField.accuracy).toFixed(1)}%`} label="Real field photos, same model" sub="what a farmer would actually get" />
          <Stat value={`${pct(tunedField.accuracy).toFixed(1)}%`} label="Field photos after adding field data" sub="better, still below usable" />
        </div>
        <div className="mt-5">
          <BarChart
            title="Accuracy on photos taken in real fields"
            caption={`${tunedField.n_images} held-out PlantDoc photos, 27 conditions.`}
            rows={[
              { label: "Guessing the most common condition", value: pct(tunedField.majority_baseline_accuracy) },
              { label: "Trained on lab photos only", value: pct(labOnlyField.accuracy) },
              { label: "Lab photos + field photos", value: pct(tunedField.accuracy), emphasis: true },
            ]}
          />
        </div>
        <p className="mt-3 text-sm text-ink-3">
          Caveat: PlantDoc photos come from the web and may include near-duplicates on both sides of our split, so the last
          number may be optimistic. One run, one seed.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">2. Saying &quot;I&apos;m not sure&quot;</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          Dehqan only answers when the model is confident, and otherwise sends the farmer to the extension office. The cost is
          that it answers fewer photos. The chart shows the trade-off for the field-trained model.
        </p>
        <div className="mt-5">
          <CoverageChart
            title="Answering fewer photos buys accuracy, slowly"
            caption="Measured on held-out field photos. Thresholds were picked on the same photos, so treat this as optimistic."
            points={curve}
            answerEverything={fieldTuned.abstention_field_tuned.answer_everything_accuracy}
            callouts={[0.5, 0.9, 0.99]}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          The live app uses a confidence threshold of 0.9. At that setting it answers about a quarter of field photos and is
          right on about four in five of those. The model is overconfident: even a 90% confidence is wrong roughly one time
          in five. That is why Dehqan always labels answers as preliminary.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">3. Other crops and cameras</h2>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <BarChart
            title="Cotton: new camera, new source"
            caption="Trained on one cotton dataset (Bangladesh), then tested on a second one from a different group. Only the 2 diseases both sets share are scored."
            rows={[
              { label: "Always guess the more common class", value: pct(cotton.cross_source_test.shared_only_2way.majority_baseline_accuracy) },
              { label: "Model on a new source", value: pct(cotton.cross_source_test.shared_only_2way.accuracy), emphasis: true },
              { label: "Model on its own source (7 classes)", value: pct(cotton.same_source_test.accuracy), sub: "likely optimistic" },
            ]}
          />
          <BarChart
            title="Corn photographed in Chinese fields"
            caption={`${corn.n_known} photos of the 2 diseases our models know. Guessing between two scores 50%.`}
            rows={[
              { label: "Guessing one of the two", value: pct(corn72.known_always_guess_one_class) },
              { label: "Lab-trained model", value: pct(cornLab.known_accuracy_all_27_classes) },
              { label: "With field photos in training", value: pct(corn72.known_accuracy_all_27_classes), emphasis: true },
            ]}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          On cotton, the model barely beats always guessing the more common class (70% vs 60%): it learned one dataset&apos;s
          look, not the disease. On corn, the lab-trained model scores below a coin flip. On four corn diseases it has never
          seen, the field-trained model still reports over 90% confidence on about {pct(corn72["unseen_share_confidence_above_0.9"]).toFixed(0)}% of photos, so a
          confidence threshold alone does not catch unknown diseases.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">4. How bad is it? Severity from the photo</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          Severity is the share of the leaf covered by spots, graded mild (under 10%), moderate (10 to 30%) or severe (30% or
          more). Our grades, not an official scale. Tested on {sev.config.n_test} field photos of apple, soybean and wheat.
        </p>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <BarChart
            title="Getting the grade right"
            rows={[
              { label: "Always guess the most common grade", value: pct(sev.naive_mean_baseline.grade_accuracy) },
              { label: "Colour thresholds, no learning", value: pct(sev.colour_threshold_baseline.grade_accuracy) },
              { label: "Learned segmentation model", value: pct(sev.learned_segmentation.grade_accuracy), emphasis: true },
            ]}
          />
          <BarChart
            title="Average error in severity (lower is better)"
            unit=" points"
            max={15}
            rows={[
              { label: "Always guess the average", value: sev.naive_mean_baseline.severity_mae_points },
              { label: "Colour thresholds, no learning", value: sev.colour_threshold_baseline.severity_mae_points },
              { label: "Learned segmentation model", value: sev.learned_segmentation.severity_mae_points, emphasis: true },
            ]}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          Wheat is the weakest crop: an average error of {sev.learned_by_crop.wheat.severity_mae_points.toFixed(1)} points, and only {pct(sev.learned_by_crop.wheat.grade_accuracy).toFixed(0)}% of grades right. Apple&apos;s
          100% is not meaningful, since every apple photo is mild. Small test set, one split.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">5. Is it even a leaf?</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          Before diagnosing, Dehqan checks that the photo shows a leaf, using the CLIP model with no extra training. We tested
          the obvious shortcut too: rejecting photos where the disease model is unsure.
        </p>
        <div className="mt-5">
          <BarChart
            title="Leaf photos accepted while wrongly accepting at most 5% of non-leaf photos"
            caption={`${gate.n_positive} leaf photos and ${gate.n_negative} non-leaf photos.`}
            rows={[
              { label: "Using the disease model's own confidence", value: pct(gate.baseline_classifier_confidence.tpr_at_5pct_fpr) },
              { label: "CLIP check", value: pct(gate.clip_gate.tpr_at_5pct_fpr), emphasis: true },
            ]}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          The check works very well on everyday objects, faces and animals. We have <strong>not</strong> tested the harder
          cases a farmer will send: bare soil, weeds, fruit, or a hand holding a leaf.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">6. Can we predict prices?</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          Dehqan only gives a sell-or-hold hint when its forecast beats the simplest possible guess: &quot;prices stay where they are&quot;.
          We replayed the last {market.n_forecasts_per_series / 3} months of retail prices for {market.n_series} crop and market series, using only data
          available at each date, and compared.
        </p>
        <div className="mt-5">
          <BarChart
            title="Average error of a 3-month price forecast (lower is better)"
            caption={`${market.n_series} series, ${market.n_forecasts_per_series} forecasts each. Source: WFP retail prices for Pakistan.`}
            unit="%"
            max={15}
            decimals={2}
            rows={[
              { label: "Prices stay the same", value: market.mean_error_pct.naive_baseline },
              { label: "Dehqan's market agent", value: market.mean_error_pct.agent, emphasis: true },
              { label: "Smoothed level and trend", value: market.fixed_method_mean_error_pct_for_context.holt_damped },
              { label: "Continue the last 12 months' trend", value: market.fixed_method_mean_error_pct_for_context.drift_12m },
              { label: "Continue the last 6 months' trend", value: market.fixed_method_mean_error_pct_for_context.drift_6m },
              { label: "Same month as last year", value: market.fixed_method_mean_error_pct_for_context.seasonal_naive },
            ]}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          <strong>No method beat &quot;prices stay the same&quot;.</strong> The agent was better on {market.series_agent_better_than_naive} of {market.n_series} series,
          slightly worse on {market.series_agent_worse_than_naive}, and tied on {market.series_tied} (it picks &quot;prices stay the same&quot; unless another method
          clearly wins in a past test). So in practice it almost always says &quot;no clear signal&quot;, and that is the honest answer. Its ranges aimed to contain
          the outcome {Math.round(market.range_coverage.target * 100)}% of the time and did {Math.round(market.range_coverage.observed_all_horizons * 100)}% overall, but only{" "}
          {Math.round(market.by_commodity.Wheat.coverage * 100)}% for wheat, whose prices have been the most volatile. These are retail prices, not what
          a farmer is paid at the mandi.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="font-display text-2xl font-semibold">7. Does it understand your question?</h2>
        <p className="mt-2 max-w-3xl text-ink-2">
          &quot;Ask Dehqan&quot; reads a question in English, Roman Urdu or Urdu and passes it to the right tool. We wrote {router.test.router.n} test questions
          (including ones it should not understand) and ran them once, at the end, after fixing mistakes on a separate set.
        </p>
        <div className="mt-5">
          <BarChart
            title="Questions understood completely right (frozen test set)"
            caption={`${router.test.router.n} questions in English, Roman Urdu and Urdu script.`}
            rows={[
              { label: "Never recognise anything", value: router.test.baseline_never_recognise_anything.exact_match * 100 },
              { label: "Always answer with the most common topic", value: router.test.baseline_always_say_weather.exact_match * 100 },
              { label: "Dehqan's router", value: router.test.router.exact_match * 100, emphasis: true },
            ]}
            decimals={0}
          />
        </div>
        <p className="mt-3 max-w-3xl text-sm text-ink-2">
          <strong>Every question asking which pesticide or what dose was refused</strong> ({router.test.router.pesticide_questions_routed_to_refusal} of {router.test.router.pesticide_questions}; the
          automated checks require 100%). It missed {router.test.router.wrong.length} questions: three describing symptoms without naming a disease
          (it then says what it can help with instead of guessing) and one where &quot;I will not spray&quot; was read as a spray question.
          The questions were written by us, so real wording will be harder: treat this as an upper bound.
        </p>
      </section>

      <section className="mt-12 rounded-2xl border border-gold/50 bg-gold-soft p-6">
        <h2 className="font-display text-2xl font-semibold">What is not solved yet</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-ink-2">
          <li>No wheat or cotton disease classifier that works on new cameras. Pakistani field photos are still needed.</li>
          <li>None of our field data comes from Pakistan (nearest public sources: China, Bangladesh).</li>
          <li>The question reader is keyword-based and was tested on questions we wrote; real farmers will word things differently.</li>
          <li>No pesticide advice. Dose and safety must come from official Pakistani documents we do not have loaded yet, and the app never invents them.</li>
          <li>The satellite field check shows greenness (NDVI), a physical measurement, but its &quot;even or patchy&quot; reading uses thresholds we chose and has not been checked against ground truth.</li>
          <li>Price forecasts do not beat the simple &quot;prices stay the same&quot; guess, so market advice is mostly &quot;no clear signal&quot;. Voice notes and satellite field checks are not built yet.</li>
        </ul>
      </section>
    </div>
  );
}
