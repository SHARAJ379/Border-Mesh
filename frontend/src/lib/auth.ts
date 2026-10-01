/**
 * Real per-officer session storage -- replaces the old single shared
 * officer password (sessionStorage key 'bordermesh_officer_key', prompted
 * via window.prompt) that gated exactly 4 endpoints with no per-user
 * identity behind it. A real login (see services/api.ts's `login`) now
 * issues a JWT tied to a specific Officer account, stored here and reused
 * by every API call, not just a handful of sensitive ones.
 *
 * localStorage, not sessionStorage: a real login is meant to persist
 * across tabs/reloads until the token expires or the officer logs out,
 * not re-prompt on every new tab the way the old single-password scheme
 * did.
 */
export interface Officer {
  badge_id: string;
  full_name: string;
}

const TOKEN_KEY = 'bordermesh_session_token';
const OFFICER_KEY = 'bordermesh_session_officer';

// Dispatched whenever the session is set or cleared, so the top-level app
// shell can re-render between the login screen and the dashboard without
// every caller needing to manually notify it.
export const SESSION_CHANGED_EVENT = 'bordermesh:session-changed';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getOfficer(): Officer | null {
  const raw = localStorage.getItem(OFFICER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Officer;
  } catch {
    return null;
  }
}

export function setSession(token: string, officer: Officer): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(OFFICER_KEY, JSON.stringify(officer));
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(OFFICER_KEY);
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
}

export function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Appends the session token as a `?token=` query parameter -- the one
 * exception to the Authorization-header rule above. An <img src="..."> tag
 * has no way to attach a custom header, so every document/face/heatmap
 * image URL returned by the API (all served through the backend's
 * decrypt-and-stream /uploads route, which accepts the token either way --
 * see backend/app/api/deps.py's get_current_officer) goes through this
 * before being used as an <img> src.
 */
export function appendToken<T extends string | undefined | null>(url: T): T {
  const token = getToken();
  if (!token || !url) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(token)}` as T;
}
