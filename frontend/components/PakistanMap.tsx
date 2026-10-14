"use client";

import Link from "next/link";
import { useState } from "react";
import pakistan from "@/data/pakistan.geo.json";
import { CITIES, type City } from "@/lib/cities";
import { useLiveWeather, type Now } from "@/lib/liveWeather";

// Simple equirectangular projection, with longitude squeezed by cos(latitude) so shapes look right.
const LON0 = 60.7;
const LAT1 = 37.3;
const SCALE = 34; // px per degree of latitude
const KX = Math.cos((30.5 * Math.PI) / 180);

const project = (lon: number, lat: number): [number, number] => [(lon - LON0) * KX * SCALE, (LAT1 - lat) * SCALE];
const W = Math.ceil((78 - LON0) * KX * SCALE);
const H = Math.ceil((LAT1 - 23.5) * SCALE);

type Geo = { features: { geometry: { coordinates: number[][][] } }[] };
const ring = (pakistan as unknown as Geo).features[0].geometry.coordinates[0];
const outline = ring.map(([lon, lat], i) => `${i ? "L" : "M"}${project(lon, lat).map((n) => n.toFixed(1)).join(",")}`).join("") + "Z";

const hhmm = (iso: string) => iso.slice(11, 16);

function ConditionLine({ now }: { now: Now }) {
  return (
    <p className="mt-1 text-sm text-ink-2">
      <span className="font-semibold text-ink">{Math.round(now.temp)}°C</span> · wind {Math.round(now.wind)} km/h ·{" "}
      {now.rain > 0 ? "raining now" : "dry now"}
    </p>
  );
}

function CityCard({ city, now, x, y }: { city: City; now?: Now; x: number; y: number }) {
  const left = (x / W) * 100;
  const top = (y / H) * 100;
  // Keep the card inside the figure: near the right edge it opens to the left, near the top it opens downward.
  const shiftX = left > 62 ? "-100%" : left < 22 ? "0%" : "-50%";
  const below = top < 30;
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-10 w-60 rounded-xl border border-green/50 bg-surface-2/95 p-3 shadow-xl backdrop-blur"
      style={{
        left: `${left}%`,
        top: `${top}%`,
        transform: `translate(${shiftX}, ${below ? "18px" : "calc(-100% - 18px)"})`,
        boxShadow: "0 12px 34px -10px var(--glow)",
      }}
    >
      <p className="flex items-baseline justify-between gap-2">
        <span className="font-display text-base font-semibold">{city.name}</span>
        <span className="font-urdu text-base text-ink-3" lang="ur" dir="rtl">{city.urdu}</span>
      </p>
      {now ? <ConditionLine now={now} /> : <p className="mt-1 text-sm text-ink-3">Loading live weather…</p>}
      <p className="mt-1 text-xs text-ink-3">{city.note}</p>
      <p className="mt-1.5 text-xs font-semibold text-green">Click for the spray window →</p>
    </div>
  );
}

export default function PakistanMap({ activeId }: { activeId?: string }) {
  const { data, failed } = useLiveWeather();
  const [hover, setHover] = useState<string | null>(null);
  // The selected city (spray page) stays highlighted, but its card opens only on hover: the page already shows its details.
  const highlightId = hover ?? activeId ?? null;
  const shown = CITIES.find((c) => c.id === hover);
  const updated = data ? hhmm(Object.values(data)[0].time) : null;

  return (
    <figure className="relative w-full">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Animated map of Pakistan with eight farming-region cities" className="h-auto w-full overflow-visible">
        <defs>
          <clipPath id="pk-clip"><path d={outline} /></clipPath>
          <linearGradient id="pk-sweep" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="var(--green-bright)" stopOpacity="0" />
            <stop offset="0.7" stopColor="var(--green-bright)" stopOpacity="0.28" />
            <stop offset="1" stopColor="var(--green-bright)" stopOpacity="0.5" />
          </linearGradient>
          <filter id="pk-glow" x="-150%" y="-150%" width="400%" height="400%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <path d={outline} fill="var(--surface-3)" stroke="var(--green)" strokeWidth={1.5} strokeLinejoin="round" />
        {/* a soft band of light slowly scanning across the country */}
        <g clipPath="url(#pk-clip)">
          <rect className="map-sweep" x={0} y={0} width={120} height={H} fill="url(#pk-sweep)" style={{ ["--sweep-end" as string]: `${W + 20}px` }} />
        </g>
        {/* marching dashes along the border */}
        <path d={outline} className="map-outline-flow" fill="none" stroke="var(--green-bright)" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />

        {CITIES.map((c, i) => {
          const [x, y] = project(c.lon, c.lat);
          const active = c.id === highlightId;
          return (
            <Link
              key={c.id}
              href={`/spray?city=${c.id}`}
              aria-label={`Spray window for ${c.name}`}
              className="map-city"
              onMouseEnter={() => setHover(c.id)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(c.id)}
              onBlur={() => setHover(null)}
            >
              <g className="cursor-pointer">
                <circle cx={x} cy={y} r={20} fill="transparent" />
                <circle className="map-ring" cx={x} cy={y} r={6} fill="none" stroke="var(--green-bright)" strokeWidth={1.6} style={{ animationDelay: `${(i * 0.37) % 2.8}s` }} />
                <circle
                  className="map-dot"
                  cx={x}
                  cy={y}
                  r={active ? 7 : 5}
                  fill={active ? "var(--gold-bright)" : "var(--green-bright)"}
                  stroke="var(--surface)"
                  strokeWidth={2}
                  filter={active ? "url(#pk-glow)" : undefined}
                />
                <text x={c.side === "r" ? x + 11 : x - 11} y={y + 4} textAnchor={c.side === "r" ? "start" : "end"} fontSize={12} fontWeight={active ? 700 : 600} fill="var(--ink)" stroke="var(--surface)" strokeWidth={3} paintOrder="stroke">
                  {c.name}
                </text>
              </g>
            </Link>
          );
        })}
      </svg>

      {shown && (() => { const [x, y] = project(shown.lon, shown.lat); return <CityCard city={shown} now={data?.[shown.id]} x={x} y={y} />; })()}

      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-3">
        {updated ? (
          <span className="flex items-center gap-1.5 font-semibold text-green">
            <span className="live-dot inline-block h-2 w-2 rounded-full" style={{ background: "var(--green-bright)" }} />
            LIVE weather, updated {updated} PKT
          </span>
        ) : failed ? (
          <span>Live weather is unavailable right now.</span>
        ) : (
          <span>Loading live weather…</span>
        )}
        <span>Hover or tap a city. Simplified outline for illustration only; not an official map.</span>
      </figcaption>
    </figure>
  );
}
