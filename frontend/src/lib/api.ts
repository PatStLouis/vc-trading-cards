/**
 * Shared API client: base URL, authenticated fetch (session cookie), and admin fetch (cookie + optional API key).
 * All authenticated and admin requests use credentials: 'include' for session cookie.
 * Admin requests optionally send X-Admin-API-Key when set via env or UI.
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export function apiUrl(): string {
  return API_BASE;
}

/** Admin API key from env (build-time) or sessionStorage (set in Admin UI). */
export function getAdminApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  const fromStorage = sessionStorage.getItem('tritone_admin_api_key');
  if (fromStorage?.trim()) return fromStorage.trim();
  const fromEnv = (import.meta.env.VITE_ADMIN_API_KEY as string)?.trim();
  return fromEnv || null;
}

export function setAdminApiKey(key: string | null): void {
  if (typeof window === 'undefined') return;
  if (key?.trim()) sessionStorage.setItem('tritone_admin_api_key', key.trim());
  else sessionStorage.removeItem('tritone_admin_api_key');
}

/**
 * Fetch from API. Use auth: true for routes that require session (e.g. /api/me, /api/wallet/*).
 */
export async function fetchApi(
  path: string,
  init: RequestInit & { auth?: boolean } = {}
): Promise<Response> {
  const { auth = false, ...rest } = init;
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  return fetch(url, {
    ...rest,
    credentials: auth ? 'include' : rest.credentials,
  });
}

/**
 * Fetch admin API. Always sends credentials; adds X-Admin-API-Key if getAdminApiKey() is set.
 */
export async function fetchAdmin(path: string, init: RequestInit = {}): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  const headers = new Headers(init.headers);
  const key = getAdminApiKey();
  if (key) headers.set('X-Admin-API-Key', key);
  return fetch(url, { ...init, headers, credentials: 'include' });
}

/** Full URL for poser DID document (user's unique username). */
export function poserDidUrl(poserUsername: string): string {
  if (!poserUsername) return '';
  return `${API_BASE}/poser/${encodeURIComponent(poserUsername)}/did.json`;
}
