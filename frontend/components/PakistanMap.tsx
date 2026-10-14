import Link from "next/link";
import pakistan from "@/data/pakistan.geo.json";
import { CITIES } from "@/lib/cities";

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

export default function PakistanMap({ activeId }: { activeId?: string }) {
  return (
    <figure className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Map of Pakistan with eight farming-region cities" className="h-auto w-full">
        <path d={outline} fill="var(--surface-3)" stroke="var(--green)" strokeWidth={2} strokeLinejoin="round" />
        {CITIES.map((c) => {
          const [x, y] = project(c.lon, c.lat);
          const active = c.id === activeId;
          return (
            <Link key={c.id} href={`/spray?city=${c.id}`} aria-label={`Spray window for ${c.name}`}>
              <g className="cursor-pointer">
                <circle cx={x} cy={y} r={14} fill="transparent" />
                <circle cx={x} cy={y} r={active ? 7 : 5} fill={active ? "var(--gold)" : "var(--green)"} stroke="var(--surface)" strokeWidth={2} />
                <text x={c.side === "r" ? x + 10 : x - 10} y={y + 4} textAnchor={c.side === "r" ? "start" : "end"} fontSize={12} fontWeight={active ? 700 : 500} fill="var(--ink)" stroke="var(--surface)" strokeWidth={3} paintOrder="stroke">
                  {c.name}
                </text>
              </g>
            </Link>
          );
        })}
      </svg>
      <figcaption className="mt-1 text-xs text-ink-3">Simplified outline for illustration only; not an official map.</figcaption>
    </figure>
  );
}
