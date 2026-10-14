"use client";

import { useEffect, useState } from "react";
import { CITIES } from "@/lib/cities";

// Real current conditions from Open-Meteo (free, no key, allows browser calls). One request covers every city.
import { parseCurrent, type Now } from "@/lib/parseCurrent";

export type { Now };

const URL =
  "https://api.open-meteo.com/v1/forecast" +
  `?latitude=${CITIES.map((c) => c.lat).join(",")}&longitude=${CITIES.map((c) => c.lon).join(",")}` +
  "&current=temperature_2m,wind_speed_10m,precipitation,is_day&timezone=Asia%2FKarachi";

const REFRESH_MS = 10 * 60 * 1000;

export function useLiveWeather(): { data: Record<string, Now> | null; failed: boolean } {
  const [data, setData] = useState<Record<string, Now> | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(URL)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((json) => {
          if (cancelled) return;
          const parsed = parseCurrent(json, CITIES.map((c) => c.id));
          if (Object.keys(parsed).length === 0) throw new Error("unexpected response");
          setData(parsed);
          setFailed(false);
        })
        .catch(() => !cancelled && setFailed(true));
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  return { data, failed };
}
