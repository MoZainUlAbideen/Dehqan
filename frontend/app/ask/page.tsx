import { Suspense } from "react";
import AskClient from "./AskClient";

export const metadata = { title: "Ask Dehqan" };

export default function AskPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">
        Ask Dehqan <span className="font-urdu text-3xl text-ink-3" lang="ur" dir="rtl">دہقان سے پوچھیں</span>
      </h1>
      <p className="mt-3 max-w-3xl text-ink-2">
        Write your question in English, Roman Urdu or Urdu. Dehqan works out whether it is about the weather and spraying, market
        prices, your field from space, or a sick plant, and passes it to the right tool. It will <strong>not</strong> name pesticides or doses.
      </p>
      <p className="font-urdu mt-1 max-w-3xl text-base text-ink-3" lang="ur" dir="rtl">
        اپنا سوال اردو یا انگریزی میں لکھیں۔ دہقان کیڑے مار ادویات کے نام یا مقدار نہیں بتاتا۔
      </p>
      <Suspense fallback={<p className="mt-8 text-ink-3">Loading…</p>}>
        <AskClient />
      </Suspense>
    </div>
  );
}
