import type { Metadata } from "next";
import { Fraunces, Inter, Noto_Nastaliq_Urdu } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const body = Inter({ variable: "--font-body", subsets: ["latin"] });
const display = Fraunces({ variable: "--font-display", subsets: ["latin"] });
const urdu = Noto_Nastaliq_Urdu({ variable: "--font-urdu", subsets: ["arabic"] });

export const metadata: Metadata = {
  title: "Dehqan: crop doctor for Pakistani farmers",
  description:
    "An honest AI crop doctor: diagnoses leaf photos, grades severity, finds safe spray windows, and says 'I'm not sure' when it isn't.",
};

const NAV = [
  { href: "/diagnose", label: "Diagnose a leaf" },
  { href: "/spray", label: "Spray window" },
  { href: "/field", label: "Field from space" },
  { href: "/market", label: "Market prices" },
  { href: "/accuracy", label: "How we measured accuracy" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable} ${urdu.variable} antialiased`}>
      <body className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur" style={{ boxShadow: "0 1px 0 0 var(--green-bright)" }}>
          <nav className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-baseline gap-3" aria-label="Dehqan home">
              <span className="font-urdu text-3xl leading-none text-green" lang="ur" dir="rtl">
                دہقان
              </span>
              <span className="font-display text-xl font-semibold tracking-tight">Dehqan</span>
            </Link>
            <ul className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm font-medium text-ink-2">
              {NAV.map((n) => (
                <li key={n.href}>
                  <Link href={n.href} className="rounded px-1 py-1 transition-colors hover:text-green">
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-line bg-surface-2">
          <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-ink-2 sm:px-6">
            <p className="font-medium text-ink">Dehqan is a research prototype, not agronomic advice.</p>
            <p className="mt-1">
              Diagnoses are preliminary AI guesses. Always confirm with your local agriculture extension office before
              spraying anything. Pesticide dose and safety guidance is not available yet.
            </p>
            <p className="font-urdu mt-2 text-base" lang="ur" dir="rtl">
              یہ ایک تحقیقی نمونہ ہے۔ کوئی بھی سپرے کرنے سے پہلے اپنے مقامی زرعی توسیعی دفتر سے ضرور تصدیق کریں۔
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
