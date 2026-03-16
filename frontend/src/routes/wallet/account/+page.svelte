<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import AppHeader from '$lib/components/AppHeader.svelte';
  import { apiUrl, fetchApi } from '$lib/api';
  import { registerPasskey, isWebAuthnAvailable } from '$lib/webauthn';

  type LinkedAccount = {
    provider: string;
    provider_user_id: string;
    provider_username: string;
    provider_avatar?: string | null;
    provider_discriminator?: string | null;
  };
  type User = {
    username: string;
    wallet_id: string;
    provider?: string;
    avatar_url?: string | null;
    accounts?: LinkedAccount[];
    has_passkey?: boolean;
    passkey_count?: number;
    pending_issued_count?: number;
    passkeys?: {
      id?: string;
      created_at: string;
      credential_device_type?: string | null;
      credential_backed_up?: boolean | null;
      attestation_format?: string | null;
      aaguid?: string | null;
      registered_name?: string | null;
    }[];
  };

  let user: User | null = $state(null);
  let loading = $state(true);
  let error = $state('');
  let passkeyAdding = $state(false);
  let passkeyMessage = $state('');
  let passkeyRemoving = $state<string | null>(null);
  let discordRefreshing = $state(false);
  let discordRefreshError = $state('');
  let twitchRefreshing = $state(false);
  let twitchRefreshError = $state('');

  const API = apiUrl();

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetchApi('/api/me', { auth: true, cache: 'no-store' });
      if (res.status === 401) {
        goto('/');
        return;
      }
      if (!res.ok) throw new Error('Failed to load account');
      user = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      user = null;
    } finally {
      loading = false;
    }
  }

  onMount(() => load());

  function hasProvider(provider: string): boolean {
    if (!user) return false;
    const p = provider.toLowerCase();
    if ((user.provider || '').toLowerCase() === p) return true;
    return (user.accounts || []).some((a) => (a.provider || '').toLowerCase() === p);
  }

  async function addPasskey() {
    if (!user || passkeyAdding || !isWebAuthnAvailable()) return;
    passkeyMessage = '';
    passkeyAdding = true;
    try {
      const data = await registerPasskey();
      passkeyMessage = data.message || 'Passkey added.';
      await load();
    } catch {
      passkeyMessage = 'Failed to add passkey';
    } finally {
      passkeyAdding = false;
    }
  }

  async function removePasskey(passkeyId: string) {
    if (!user || !passkeyId || passkeyRemoving) return;
    passkeyMessage = '';
    passkeyRemoving = passkeyId;
    try {
      const res = await fetchApi(`/api/me/passkeys/${encodeURIComponent(passkeyId)}`, { method: 'DELETE', auth: true });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        passkeyMessage = data.detail || 'Failed to remove passkey';
        return;
      }
      await load();
    } catch {
      passkeyMessage = 'Failed to remove passkey';
    } finally {
      passkeyRemoving = null;
    }
  }

  function providerLabel(p: string): string {
    return p.toLowerCase() === 'discord' ? 'Discord' : p.toLowerCase() === 'twitch' ? 'Twitch' : p;
  }

  /** Discord display: username#discriminator when discriminator is present and not "0", else username. */
  function discordDisplayName(acc: LinkedAccount | undefined): string {
    if (!acc) return 'Linked';
    const name = acc.provider_username || '';
    const disc = acc.provider_discriminator;
    if (disc != null && String(disc).trim() !== '' && String(disc).trim() !== '0') return `${name}#${disc}`;
    return name || 'Linked';
  }

  /** Display name for Discord row: prefer account data, fall back to session username so we never show "Linked" when connected. */
  function discordRowDisplayName(acc: LinkedAccount | undefined, sessionUsername: string | undefined): string {
    const fromAcc = discordDisplayName(acc);
    if (fromAcc !== 'Linked') return fromAcc;
    return sessionUsername || 'Connected';
  }

  async function refreshDiscordProfile() {
    if (!user || discordRefreshing) return;
    discordRefreshError = '';
    discordRefreshing = true;
    try {
      const res = await fetchApi('/api/me/refresh-discord', { method: 'POST', auth: true });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        discordRefreshError = data.detail || 'Refresh failed';
        return;
      }
      await load();
    } catch {
      discordRefreshError = 'Refresh failed';
    } finally {
      discordRefreshing = false;
    }
  }

  async function refreshTwitchProfile() {
    if (!user || twitchRefreshing) return;
    twitchRefreshError = '';
    twitchRefreshing = true;
    try {
      const res = await fetchApi('/api/me/refresh-twitch', { method: 'POST', auth: true });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        twitchRefreshError = data.detail || 'Refresh failed';
        return;
      }
      await load();
    } catch {
      twitchRefreshError = 'Refresh failed';
    } finally {
      twitchRefreshing = false;
    }
  }

  function passkeyDeviceLabel(deviceType: string | null | undefined): string {
    if (!deviceType) return '';
    if (deviceType === 'multi_device') return 'Multi-device';
    if (deviceType === 'single_device') return 'Single device';
    return deviceType;
  }

  function passkeyDeviceSyncSummary(
    deviceType: string | null | undefined,
    backedUp: boolean | null | undefined
  ): string {
    const device = passkeyDeviceLabel(deviceType);
    const sync = backedUp == null ? '' : backedUp ? 'synced' : 'local';
    if (!device && !sync) return '';
    if (!device) return sync ? 'Synced' : 'Local';
    if (!sync) return device;
    return `${device}, ${sync}`;
  }

  function passkeyFormatLabel(fmt: string | null | undefined): string {
    if (!fmt) return '';
    const m: Record<string, string> = {
      none: 'Software',
      packed: 'Hardware',
      apple: 'Apple',
      tpm: 'TPM',
      'fido-u2f': 'FIDO U2F',
      'android-key': 'Android',
      'android-safetynet': 'Android SafetyNet',
    };
    return m[fmt] || fmt;
  }

  /** One-line label: registered name (if present), then device/sync + format. */
  function passkeyLabel(passkey: { registered_name?: string | null; credential_device_type?: string | null; credential_backed_up?: boolean | null; attestation_format?: string | null }): string {
    const deviceSync = passkeyDeviceSyncSummary(passkey.credential_device_type, passkey.credential_backed_up);
    const format = passkeyFormatLabel(passkey.attestation_format);
    const meta = [deviceSync, format].filter(Boolean);
    const metaStr = meta.length ? meta.join(' · ') : '';
    if (passkey.registered_name?.trim()) {
      return metaStr ? `${passkey.registered_name.trim()} · ${metaStr}` : passkey.registered_name.trim();
    }
    return metaStr || 'Passkey';
  }
</script>

<svelte:head>
  <title>Account · Brutality Cards</title>
</svelte:head>

<div class="app-page py-8 px-4 md:py-10 relative">
  <div class="app-page__bg" aria-hidden="true"></div>
  <div class="texture-overlay" aria-hidden="true"></div>

  <div class="relative z-10 max-w-xl mx-auto space-y-4">
    <AppHeader title="Account" {user} showExploreButton={false} />

    {#if loading}
      <div class="rounded-xl border border-border/80 bg-card/50 py-8 text-center text-sm text-muted-foreground">Loading…</div>
    {:else if error}
      <div class="rounded-xl border border-destructive/50 bg-card/50 p-4">
        <p class="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" class="mt-2" onclick={load}>Retry</Button>
      </div>
    {:else if user}
      <!-- Linked accounts -->
      <section class="rounded-xl border border-border/80 bg-card/50 overflow-hidden">
        <div class="px-4 py-3 border-b border-border/60">
          <h2 class="text-sm font-semibold text-foreground">Linked accounts</h2>
          <p class="text-xs text-muted-foreground mt-0.5">Connect Discord or Twitch to log in.</p>
        </div>
        <div class="p-3 space-y-3">
          {#each ['discord', 'twitch'] as provider}
            {@const linked = hasProvider(provider)}
            {@const isDiscord = provider === 'discord'}
            <div
              class="linked-card flex items-center gap-3 rounded-xl px-4 py-3 transition-colors {isDiscord
                ? 'linked-card--discord border border-[#5865F2]/20 bg-[#5865F2]/5 hover:bg-[#5865F2]/10'
                : 'linked-card--twitch border border-[#9146FF]/20 bg-[#9146FF]/5 hover:bg-[#9146FF]/10'} {!linked ? 'opacity-80' : ''}"
            >
              <div class="flex items-center gap-3 min-w-0 flex-1">
                {#if isDiscord && linked}
                  {@const acc = user.accounts?.find((a) => (a.provider || '').toLowerCase() === provider)}
                  {#if user.avatar_url}
                    <img
                      src={user.avatar_url}
                      alt=""
                      class="size-10 shrink-0 rounded-full bg-muted object-cover ring-2 ring-background shadow-sm"
                      width="40"
                      height="40"
                    />
                  {:else}
                    <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#5865F2] text-white text-sm font-semibold shadow-sm ring-2 ring-background" aria-hidden="true">D</span>
                  {/if}
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="text-sm font-semibold text-foreground">{providerLabel(provider)}</span>
                      <span class="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-600 dark:text-emerald-400">Connected</span>
                    </div>
                    <p class="text-xs text-muted-foreground truncate mt-0.5" title={discordRowDisplayName(acc, user.username)}>{discordRowDisplayName(acc, user.username)}</p>
                  </div>
                {:else if isDiscord && !linked}
                  <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#5865F2]/30 text-[#5865F2] dark:bg-[#5865F2]/20" aria-hidden="true">
                    <svg class="size-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
                  </span>
                  <div class="min-w-0">
                    <span class="text-sm font-semibold text-foreground">{providerLabel(provider)}</span>
                    <p class="text-xs text-muted-foreground mt-0.5">Link your account to sign in with Discord</p>
                  </div>
                {:else}
                  <!-- Twitch -->
                  {#if linked}
                    {@const acc = user.accounts?.find((a) => (a.provider || '').toLowerCase() === provider)}
                    {#if acc?.provider_avatar}
                      <img
                        src={acc.provider_avatar}
                        alt=""
                        class="size-10 shrink-0 rounded-full bg-muted object-cover ring-2 ring-background shadow-sm"
                        width="40"
                        height="40"
                      />
                    {:else}
                      <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#9146FF]/30 text-[#9146FF] dark:bg-[#9146FF]/40" aria-hidden="true">
                        <svg class="size-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"/></svg>
                      </span>
                    {/if}
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-sm font-semibold text-foreground">{providerLabel(provider)}</span>
                        <span class="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-600 dark:text-emerald-400">Connected</span>
                      </div>
                      <p class="text-xs text-muted-foreground truncate mt-0.5">{acc?.provider_username || 'Linked'}</p>
                    </div>
                  {:else}
                    <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#9146FF]/30 text-[#9146FF] dark:bg-[#9146FF]/20" aria-hidden="true">
                      <svg class="size-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"/></svg>
                    </span>
                    <div class="min-w-0">
                      <span class="text-sm font-semibold text-foreground">{providerLabel(provider)}</span>
                      <p class="text-xs text-muted-foreground mt-0.5">Link your account to sign in with Twitch</p>
                    </div>
                  {/if}
                {/if}
              </div>
              <div class="flex items-center shrink-0">
                {#if isDiscord && linked}
                  <button
                    type="button"
                    class="linked-card__refresh rounded-lg p-2 text-muted-foreground hover:text-[#5865F2] hover:bg-[#5865F2]/15 transition-colors disabled:opacity-50"
                    onclick={refreshDiscordProfile}
                    disabled={discordRefreshing}
                    title="Refresh avatar and username from Discord (no login required)"
                    aria-label="Refresh Discord profile"
                  >
                    <svg class="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                  {#if discordRefreshError}
                    <p class="text-xs text-amber-600 dark:text-amber-400 ml-1">{discordRefreshError}</p>
                  {/if}
                {:else if !isDiscord && linked}
                  <button
                    type="button"
                    class="linked-card__refresh rounded-lg p-2 text-muted-foreground hover:text-[#9146FF] hover:bg-[#9146FF]/15 transition-colors disabled:opacity-50"
                    onclick={refreshTwitchProfile}
                    disabled={twitchRefreshing}
                    title="Refresh avatar and username from Twitch (no login required)"
                    aria-label="Refresh Twitch profile"
                  >
                    <svg class="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                  {#if twitchRefreshError}
                    <p class="text-xs text-amber-600 dark:text-amber-400 ml-1">{twitchRefreshError}</p>
                  {/if}
                {:else if !linked}
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-8 text-xs shrink-0"
                    onclick={() => { window.location.href = `${API}/auth/login?provider=${provider}`; }}
                  >
                    Link
                  </Button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </section>

      <!-- Passkey -->
      <section class="rounded-xl border border-border/80 bg-card/50 overflow-hidden">
        <div class="px-4 py-2.5 border-b border-border/60">
          <h2 class="text-sm font-semibold text-foreground">Passkey</h2>
          <p class="text-xs text-muted-foreground mt-0.5">Sign in with fingerprint, face, or security key.</p>
        </div>
        <div class="p-3 space-y-2">
          {#if isWebAuthnAvailable()}
            {#if (user.passkeys?.length ?? 0) > 0}
              <ul class="space-y-1.5 text-sm" role="list">
                {#each (user.passkeys ?? []) as passkey}
                  <li class="flex items-center gap-2 rounded-lg bg-background/60 px-2.5 py-2 min-h-[2.25rem]">
                    <span class="text-muted-foreground shrink-0 text-xs" aria-hidden="true">🔐</span>
                    <div class="min-w-0 flex-1">
                      <span class="text-xs font-medium block">{passkeyLabel(passkey)}</span>
                      {#if passkey.created_at}
                        {@const date = new Date(passkey.created_at.replace(' ', 'T'))}
                        <span class="text-[10px] text-muted-foreground">{date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                      {/if}
                    </div>
                    {#if passkey.id}
                      <button
                        type="button"
                        class="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                        aria-label="Remove passkey"
                        title="Remove passkey"
                        disabled={passkeyRemoving === passkey.id}
                        onclick={() => removePasskey(passkey.id!)}
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
            <Button
              variant="outline"
              size="sm"
              class="h-7 text-xs w-full sm:w-auto"
              onclick={addPasskey}
              disabled={passkeyAdding}
            >
              {passkeyAdding ? 'Adding…' : (user.passkey_count ?? 0) > 0 ? 'Add another passkey' : 'Add passkey'}
            </Button>
            {#if passkeyMessage}
              <p class="text-xs {passkeyMessage === 'Failed to add passkey' ? 'text-destructive' : 'text-muted-foreground'}">{passkeyMessage}</p>
            {/if}
          {:else}
            <p class="text-xs text-muted-foreground">Passkeys are not supported in this browser.</p>
          {/if}
        </div>
      </section>
    {/if}
  </div>
</div>

