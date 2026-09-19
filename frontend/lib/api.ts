const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiErrorEnvelope = {
  error: { code: string; message: string; details: unknown };
};

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

type FetchOptions = {
  token?: string | null;
  method?: string;
  body?: unknown;
};

async function request<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (typeof body === "object" && body !== null && "error" in body) {
      const err = (body as ApiErrorEnvelope).error;
      throw new ApiError(String(err.code), String(err.message), res.status);
    }
    throw new ApiError("HTTP_ERROR", `API request failed: ${res.status}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type HealthResponse = { status: string; service: string; version: string };
export type ReadyResponse = { status: string; database: string };

export function getApiHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/v1/health");
}

export function getApiReady(): Promise<ReadyResponse> {
  return request<ReadyResponse>("/api/v1/ready");
}

export function apiBaseUrl(): string {
  return API_BASE;
}

// ---- Identity types ----

export type Role =
  | "UNIVERSITY_ADMIN"
  | "DEPARTMENT_ADMIN"
  | "FACULTY"
  | "STAFF"
  | "CLASS_REP"
  | "STUDENT";

export type IdentityStatus = "PENDING" | "VERIFIED" | "REJECTED";

export type University = {
  id: string;
  name: string;
  code: string;
  email_domain: string;
  city: string | null;
  country: string | null;
};

export type ClassInfo = {
  id: string;
  batch_id: string;
  name: string;
  code: string;
  batch_name: string | null;
  program_name: string | null;
  department_name: string | null;
};

export type Identity = {
  id: string;
  university_id: string;
  university_name: string | null;
  role: Role;
  status: IdentityStatus;
  student_no: string | null;
  class_id: string | null;
  class_name: string | null;
  verified_at: string | null;
};

export type Profile = { display_name: string | null; bio: string | null };

export type Me = {
  id: string;
  email: string;
  profile: Profile;
  identities: Identity[];
};

export type AuthResponse = { token: string; expires_at: string; user: Me };

export type RegisterInput = {
  email: string;
  password: string;
  display_name: string;
  university_id: string;
  class_id: string;
  student_no: string;
  enrollment_code: string;
};

// ---- Identity API ----

export function listUniversities(): Promise<University[]> {
  return request<University[]>("/api/v1/universities");
}

export function listClasses(universityId: string): Promise<ClassInfo[]> {
  return request<ClassInfo[]>(`/api/v1/universities/${universityId}/classes`);
}

export function register(input: RegisterInput): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/register", { body: input });
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/api/v1/auth/login", { body: { email, password } });
}

export function logout(token: string): Promise<void> {
  return request<void>("/api/v1/auth/logout", { token });
}

export function fetchMe(token: string): Promise<Me> {
  return request<Me>("/api/v1/auth/me", { token });
}

export function updateProfile(token: string, input: { display_name?: string; bio?: string }): Promise<Profile> {
  return request<Profile>("/api/v1/auth/profile", { token, method: "PATCH", body: input });
}
