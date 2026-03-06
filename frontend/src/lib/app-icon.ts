/**
 * App icon URL from env (VITE_APP_ICON_URL). Fallback to /favicon.png when unset.
 * Use for headers, nav, QR code center, etc.
 */
export const APP_ICON_URL =
  (import.meta.env.VITE_APP_ICON_URL as string | undefined)?.trim() || '/favicon.png';
