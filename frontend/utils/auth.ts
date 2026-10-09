/**
 * Auth utilities for the dashboard session.
 *
 * The session is an HttpOnly cookie set by the backend's OAuth callback, so JavaScript
 * never sees the token (XSS cannot exfiltrate it). Every request must therefore:
 *   - send cookies   -> `credentials: "include"`
 *   - prove it came from our own JS, not a cross-site form -> `X-Requested-With` header,
 *     which the backend requires on cookie-authenticated POST/PUT/PATCH/DELETE (CSRF guard).
 */

export const CSRF_HEADER = "X-Requested-With";
export const CSRF_HEADER_VALUE = "XMLHttpRequest";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** Headers every dashboard request to the API should carry. */
export function sessionHeaders(extra: HeadersInit = {}): Record<string, string> {
  return { [CSRF_HEADER]: CSRF_HEADER_VALUE, ...headersToRecord(extra) };
}

/** `fetch` init for a cookie-authenticated API call. */
export function withSession(options: RequestInit = {}): RequestInit {
  return {
    ...options,
    credentials: "include",
    headers: sessionHeaders(options.headers ?? {}),
  };
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, withSession(options));
}

/** Ask the backend to clear the session cookie. Safe to call when already logged out. */
export async function logoutSession(): Promise<void> {
  try {
    await fetch(`${API_URL}/auth/logout`, withSession({ method: "POST" }));
  } catch {
    // Network failure: the cookie expires on its own; nothing sensitive is left client-side.
  }
}

function headersToRecord(h: HeadersInit): Record<string, string> {
  if (h instanceof Headers) {
    const out: Record<string, string> = {};
    h.forEach((v, k) => {
      out[k] = v;
    });
    return out;
  }
  if (Array.isArray(h)) return Object.fromEntries(h);
  return { ...(h as Record<string, string>) };
}
