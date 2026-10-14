// Typed client for the Dehqan FastAPI backend.
// Local development talks to a local backend. Production builds default to the deployed Render API, so Vercel needs
// no environment variable; set NEXT_PUBLIC_API_URL to point somewhere else.
const PRODUCTION_API = "https://dehqan.onrender.com";
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? (process.env.NODE_ENV === "production" ? PRODUCTION_API : "http://127.0.0.1:8000");

export type DiagnosisResult = {
  status: "not_a_crop" | "uncertain" | "diagnosis";
  message: string;
  crop_score: number | null;
  label: string | null;
  confidence: number | null;
  is_healthy: boolean | null;
  severity: number | null; // 0..1
  severity_grade: "mild" | "moderate" | "severe" | null;
  limitations: string[];
};

export type SprayWindow = {
  start: string; // local ISO time of first safe hour
  end: string; // local ISO time of last safe hour (inclusive)
  hours: number;
  max_wind_kmh: number;
  max_rain_prob_pct: number;
};

export type SprayResponse = {
  forecast_start: string | null; // local ISO time of the first forecast hour
  forecast_hours: number;
  windows: SprayWindow[];
  note: string;
  message: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = "Please check the values you entered.";
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new ApiError("This took too long. The free server may be busy; please try again in a minute.", 0);
    }
    throw new ApiError("Cannot reach the Dehqan server. Is the backend running?", 0);
  }
}

export async function diagnose(file: File): Promise<DiagnosisResult> {
  const form = new FormData();
  form.append("file", file);
  return parse(await request(`${API_URL}/diagnose`, { method: "POST", body: form }));
}

export async function sprayWindow(lat: number, lon: number): Promise<SprayResponse> {
  return parse(
    await request(`${API_URL}/spray-window`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lat, lon }),
    }),
  );
}

// ---------- market prices ----------
export type MarketOptions = {
  commodities: { name: string; unit: string; markets: string[] }[];
  data_as_of: string; // YYYY-MM
  source: string;
};

export type MarketAnalysis = {
  commodity: string;
  market: string;
  unit: string;
  data_as_of: string;
  last_price: number;
  history: { month: string; price: number }[];
  forecast: { month: string; price: number; low: number; high: number }[];
  method: { name: string; description: string; beats_naive: boolean; past_error_pct: number; naive_error_pct: number; n_past_forecasts: number };
  signal: "hold" | "sell" | "none";
  message: string;
  caveats: string[];
  track_record?: {
    months_checked: number;
    range_target: number;
    range_actually_contained_outcome: number | null;
    agent_error_pct: number | null;
    naive_error_pct: number | null;
    note: string;
  };
  source: string;
};

export async function marketOptions(): Promise<MarketOptions> {
  return parse(await request(`${API_URL}/market/options`));
}

export async function marketAnalysis(commodity: string, market: string): Promise<MarketAnalysis> {
  const q = new URLSearchParams({ commodity, market });
  return parse(await request(`${API_URL}/market?${q}`));
}

// ---------- satellite field check ----------
export type FieldPoint = {
  date: string; // YYYY-MM-DD
  tile_cloud_pct: number;
  valid_fraction: number;
  mean: number | null;
  median: number | null;
  p10: number | null;
  p90: number | null;
  spread: number | null;
  assessment: { pattern: "bare" | "even" | "patchy" | "mixed" | "unknown"; message: string; lagging_fraction: number | null };
  grid: (number | null)[][]; // NDVI per cell, null where cloudy
};

export type FieldReport = {
  center: { lat: number; lon: number };
  size_m: number;
  scenes_found: number;
  scenes_used: number;
  scenes_failed: number;
  scenes_timed_out: number;
  seconds: number;
  points: FieldPoint[];
  latest: FieldPoint | null;
  last_year: { now: number; last_year: number; change_pct: number; last_year_date?: string } | null;
  message: string;
  caveats: string[];
  source: string;
};

export async function fieldNdvi(lat: number, lon: number, size_m = 300): Promise<FieldReport> {
  return parse(
    await request(`${API_URL}/field-ndvi`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lat, lon, size_m }),
      signal: AbortSignal.timeout(150_000),
    }),
  );
}
