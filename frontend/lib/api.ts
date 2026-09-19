const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiErrorEnvelope = {
  error: { code: string; message: string; details: unknown };
};

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    const message =
      typeof body === "object" && body !== null && "error" in body
        ? String((body as ApiErrorEnvelope).error.message)
        : `API request failed: ${res.status}`;
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export type HealthResponse = { status: string; service: string; version: string };
export type ReadyResponse = { status: string; database: string };

export function getApiHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/v1/health");
}

export function getApiReady(): Promise<ReadyResponse> {
  return fetchJson<ReadyResponse>("/api/v1/ready");
}

export function apiBaseUrl(): string {
  return API_BASE;
}
