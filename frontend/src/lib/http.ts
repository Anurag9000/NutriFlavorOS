export const TOKEN_KEY = "nutriflavor_token";
export const USER_KEY = "nfos_user";

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const API_BASE = (
  configuredBase?.trim()
  || (import.meta.env.DEV ? "http://localhost:8000/api/v1" : "/api/v1")
).replace(/\/$/, "");

export class ApiClientError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(extractErrorMessage(detail, status));
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
  }
}

export function extractErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (Array.isArray(payload)) {
    const messages = payload
      .map((value) => extractValidationMessage(value))
      .filter((value): value is string => Boolean(value));
    if (messages.length) return messages.join("; ");
  }
  if (payload && typeof payload === "object") {
    const body = payload as Record<string, unknown>;
    const detail = body.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((value) => extractValidationMessage(value))
        .filter((value): value is string => Boolean(value));
      if (messages.length) return messages.join("; ");
    }
    if (detail && typeof detail === "object") {
      const nested = detail as Record<string, unknown>;
      if (typeof nested.message === "string" && nested.message.trim()) {
        return nested.message;
      }
      if (typeof nested.code === "string" && nested.code.trim()) {
        return nested.code.replaceAll("_", " ");
      }
    }
    if (typeof body.message === "string" && body.message.trim()) {
      return body.message;
    }
  }
  return `Request failed with status ${status}`;
}

function extractValidationMessage(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const message = typeof item.msg === "string"
    ? item.msg
    : typeof item.message === "string"
      ? item.message
      : null;
  if (!message) return null;
  const location = Array.isArray(item.loc)
    ? item.loc.filter((part) => typeof part === "string" || typeof part === "number").join(".")
    : "";
  return location ? `${location}: ${message}` : message;
}

function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new CustomEvent("nutriflavor:unauthorized"));
}

async function decodeResponse(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) return undefined;
  const raw = await response.text();
  if (!raw) return undefined;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(raw) as unknown;
    } catch {
      return raw;
    }
  }
  return raw;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    options.body !== undefined
    && !(options.body instanceof FormData)
    && !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload = await decodeResponse(response);
  if (response.status === 401) clearSession();
  if (!response.ok) throw new ApiClientError(response.status, payload);
  return payload as T;
}
