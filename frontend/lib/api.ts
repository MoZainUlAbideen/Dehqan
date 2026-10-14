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
  } catch {
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
