/**
 * API utility functions with automatic session expiration handling
 */
import { withSession } from './auth';

export class SessionExpiredError extends Error {
  constructor() {
    super('Session expired');
    this.name = 'SessionExpiredError';
  }
}

/**
 * Get the full API URL
 */
function getApiUrl(path: string): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  // Remove leading slash from path if it exists to avoid double slashes
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${baseUrl}/${cleanPath}`;
}

/**
 * Fetch wrapper that handles session expiration
 */
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  // Convert relative URLs to full API URLs
  const fullUrl = url.startsWith('http') ? url : getApiUrl(url);

  // Session is an HttpOnly cookie: send credentials + CSRF header, no token in JS
  const response = await fetch(fullUrl, withSession(options));

  // Check for 401 Unauthorized (session expired)
  if (response.status === 401) {
    window.location.href = '/login';
    throw new SessionExpiredError();
  }

  return response;
}

/**
 * Fetch JSON with auth and session handling
 */
export async function fetchJSON<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetchWithAuth(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
