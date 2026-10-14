// Parsing of Open-Meteo's multi-location "current conditions" response. Pure, so it can be tested without a browser.
export type Now = { temp: number; wind: number; rain: number; isDay: boolean; time: string };

/** Open-Meteo returns one object per requested point, in order. Returns {} if the shape is not what we expect. */
export function parseCurrent(payload: unknown, ids: string[]): Record<string, Now> {
  if (!Array.isArray(payload) || payload.length !== ids.length) return {};
  const out: Record<string, Now> = {};
  payload.forEach((p, i) => {
    const c = (p as { current?: Record<string, number | string> }).current;
    if (!c || typeof c.temperature_2m !== "number") return;
    out[ids[i]] = {
      temp: c.temperature_2m,
      wind: Number(c.wind_speed_10m),
      rain: Number(c.precipitation),
      isDay: c.is_day === 1,
      time: String(c.time),
    };
  });
  return out;
}
