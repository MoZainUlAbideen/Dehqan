import MarketClient from "./MarketClient";

export const metadata = { title: "Market prices | Dehqan" };

export default function MarketPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">
        Market prices <span className="font-urdu text-3xl text-ink-3" lang="ur" dir="rtl">منڈی کے نرخ</span>
      </h1>
      <p className="mt-3 max-w-3xl text-ink-2">
        Past prices and a careful three-month look ahead, to help you think about selling now or waiting. These are
        <strong> retail prices</strong> from market monitoring, not what you are paid at the mandi, and the forecast is
        often <strong>no better than assuming prices stay the same</strong>. When that is so, Dehqan says it.
      </p>
      <p className="font-urdu mt-1 max-w-3xl text-base text-ink-3" lang="ur" dir="rtl">
        یہ خوردہ قیمتیں ہیں، منڈی میں کسان کو ملنے والا بھاؤ نہیں۔ یہ صرف ایک اندازہ ہے، مشورہ نہیں۔
      </p>
      <MarketClient />
    </div>
  );
}
