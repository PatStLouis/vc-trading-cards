/**
 * WebAuthn (passkey) helpers for registration and authentication.
 * Uses the Credential Management API; options/verify go to the backend.
 */

import { apiUrl } from '$lib/api';

const API = apiUrl();

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlToBuffer(s: string): ArrayBuffer {
  const base64 = s.replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4;
  const padded = pad ? base64 + '='.repeat(4 - pad) : base64;
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/** Convert PublicKeyCredential to a JSON-serializable object for the server. */
function credentialToJSON(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response as AuthenticatorAttestationResponse | AuthenticatorAssertionResponse;
  const result: Record<string, unknown> = {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {} as Record<string, string>,
  };
  const r = result.response as Record<string, string>;
  r.clientDataJSON = bufferToBase64url(response.clientDataJSON);
  if ('attestationObject' in response) {
    r.attestationObject = bufferToBase64url((response as AuthenticatorAttestationResponse).attestationObject);
  }
  if ('authenticatorData' in response) {
    r.authenticatorData = bufferToBase64url((response as AuthenticatorAssertionResponse).authenticatorData);
  }
  if ('signature' in response) {
    r.signature = bufferToBase64url((response as AuthenticatorAssertionResponse).signature);
  }
  if ('userHandle' in response && (response as AuthenticatorAssertionResponse).userHandle) {
    r.userHandle = bufferToBase64url((response as AuthenticatorAssertionResponse).userHandle!);
  }
  return result;
}

/** Check if WebAuthn is available. */
export function isWebAuthnAvailable(): boolean {
  return typeof window !== 'undefined' && window.PublicKeyCredential != null;
}

/** Register a new passkey (requires existing session). */
export async function registerPasskey(): Promise<{ ok: boolean; message?: string }> {
  const optsRes = await fetch(`${API}/auth/webauthn/register/options`, { credentials: 'include' });
  if (!optsRes.ok) {
    const err = await optsRes.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to get registration options');
  }
  const options = await optsRes.json();
  const createOptions: CredentialCreationOptions = {
    publicKey: {
      ...options,
      challenge: base64urlToBuffer(options.challenge),
      user: {
        ...options.user,
        id: base64urlToBuffer(options.user.id),
      },
      excludeCredentials: (options.excludeCredentials || []).map((c: { id: string }) => ({
        ...c,
        id: base64urlToBuffer(c.id),
      })),
    },
  };
  const credential = await navigator.credentials.create(createOptions);
  if (!credential || !(credential instanceof PublicKeyCredential)) {
    throw new Error('Could not create passkey');
  }
  const verifyRes = await fetch(`${API}/auth/webauthn/register/verify`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentialToJSON(credential)),
  });
  const data = await verifyRes.json().catch(() => ({}));
  if (!verifyRes.ok) {
    throw new Error(data.detail || 'Verification failed');
  }
  return data;
}

/** Authenticate with passkey and log in. Returns redirect path on success. */
export async function loginWithPasskey(): Promise<{ ok: boolean; redirect?: string }> {
  const optsRes = await fetch(`${API}/auth/webauthn/login/options`);
  if (!optsRes.ok) {
    const err = await optsRes.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to get login options');
  }
  const options = await optsRes.json();
  const getOptions: CredentialRequestOptions = {
    publicKey: {
      ...options,
      challenge: base64urlToBuffer(options.challenge),
    },
  };
  const credential = await navigator.credentials.get(getOptions);
  if (!credential || !(credential instanceof PublicKeyCredential)) {
    throw new Error('Could not get passkey');
  }
  const verifyRes = await fetch(`${API}/auth/webauthn/login/verify`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentialToJSON(credential)),
  });
  const data = await verifyRes.json().catch(() => ({}));
  if (!verifyRes.ok) {
    throw new Error(data.detail || 'Verification failed');
  }
  return data;
}
