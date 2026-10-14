import { Suspense } from "react";
import FieldClient from "./FieldClient";

export const metadata = { title: "Field check from space | Dehqan" };

export default function FieldPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">
        Check a field from space <span className="font-urdu text-3xl text-ink-3" lang="ur" dir="rtl">خلا سے کھیت کی جانچ</span>
      </h1>
      <p className="mt-3 max-w-3xl text-ink-2">
        Drop a pin on your field. Dehqan looks at the last year of free <strong>Sentinel-2</strong> satellite pictures of that spot and
        shows how green the ground was on each clear day, and whether the greenness is <strong>even across the field or lower in one patch</strong>.
        It shows <em>what</em> the satellite sees, not <em>why</em>.
      </p>
      <p className="font-urdu mt-1 max-w-3xl text-base text-ink-3" lang="ur" dir="rtl">
        یہ سیٹلائٹ کی تصویر سے صرف یہ دکھاتا ہے کہ کھیت کتنا ہرا ہے، یہ نہیں کہ کیوں۔ یہ بیماری کی تشخیص نہیں ہے۔
      </p>
      <Suspense fallback={<p className="mt-8 text-ink-3">Loading…</p>}>
        <FieldClient />
      </Suspense>
    </div>
  );
}
