import DiagnoseClient from "./DiagnoseClient";

export const metadata = { title: "Diagnose a leaf | Dehqan" };

export default function DiagnosePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-4xl font-semibold tracking-tight">Diagnose a leaf</h1>
      <p className="mt-3 max-w-2xl text-ink-2">
        Send one clear, close photo of a single leaf. Dehqan first checks that it really is a leaf, then names the likely
        problem, and says <em>&quot;I&apos;m not sure&quot;</em> when it is not confident, instead of guessing.
      </p>
      <DiagnoseClient />
    </div>
  );
}
