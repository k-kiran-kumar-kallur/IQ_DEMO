import type { DemoUser, HistoryRow, IngestState, LoginAudit, Me, Result, SettingField, Status } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Called whenever the backend says the session is missing or expired, so the app can show the sign-in page. */
let onUnauthorized: () => void = () => undefined;
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (res.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      msg = body.detail || msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    call<Me>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => call<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => call<Me>("/auth/me"),
  demoUsers: () => call<{ users: DemoUser[]; password_hint: string }>("/auth/demo-users"),
  users: () => call<Me[]>("/users"),
  loginAudit: () => call<LoginAudit[]>("/login-audit"),
  status: () => call<Status>("/status"),
  samples: () => call<string[]>("/samples"),
  history: () => call<HistoryRow[]>("/history"),
  historyItem: (id: number) => call<Result>(`/history/${id}`),
  ask: (question: string) => call<Result>("/ask", { method: "POST", body: JSON.stringify({ question }) }),
  settings: () => call<Record<string, SettingField>>("/settings"),
  saveSettings: (values: Record<string, string>) =>
    call<Record<string, SettingField>>("/settings", { method: "POST", body: JSON.stringify({ values }) }),
  testNeo4j: () => call<{ ok: boolean; error?: string; ms?: number; nodes?: number }>("/settings/test-neo4j", { method: "POST" }),
  ingest: (reset: boolean) => call<IngestState>("/ingest", { method: "POST", body: JSON.stringify({ reset }) }),
  ingestStatus: () => call<IngestState>("/ingest/status"),
  fileUrl: (rawPath: string) => `/api/file?path=${encodeURIComponent(rawPath)}`,
};
