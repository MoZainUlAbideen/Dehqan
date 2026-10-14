import { Suspense } from "react";
import SprayClient from "./SprayClient";

export const metadata = { title: "Spray window | Dehqan" };

export default function SprayPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">When is it safe to spray?</h1>
      <p className="mt-3 max-w-2xl text-ink-2">
        Pick your area. Dehqan reads the next five days of weather from Open-Meteo and marks the hours with low wind, no rain
        coming, and mild heat, so spray does not drift or wash off.
      </p>
      <Suspense fallback={<p className="mt-8 text-ink-3">Loading…</p>}>
        <SprayClient />
      </Suspense>
    </div>
  );
}
