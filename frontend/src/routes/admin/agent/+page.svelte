<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import { fetchAdmin, getAdminApiKey, setAdminApiKey } from '$lib/api';

  type AgentSettings = {
    admin_url: string;
    admin_url_configured: boolean;
    api_key_configured: boolean;
    innkeeper_configured: boolean;
    discord_bot_configured: boolean;
    discord_bot_invite_url: string | null;
    status: {
      configured: boolean;
      reachable?: boolean;
      version?: string;
      label?: string;
      detail?: string;
    };
  };

  let settings: AgentSettings | null = $state(null);
  let loading = $state(true);
  let error = $state('');
  let discordRegistering = $state(false);
  let discordRegisterMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);
  let adminApiKeyInput = $state('');

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetchAdmin('/api/admin/agent/settings');
      if (!res.ok) throw new Error('Failed to load agent settings');
      settings = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      settings = null;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    load();
    adminApiKeyInput = getAdminApiKey() ?? '';
  });

  function saveAdminApiKey() {
    setAdminApiKey(adminApiKeyInput.trim() || null);
  }
  function clearAdminApiKey() {
    adminApiKeyInput = '';
    setAdminApiKey(null);
  }

  async function registerDiscordCommands() {
    if (!settings?.discord_bot_configured) return;
    discordRegisterMessage = null;
    discordRegistering = true;
    try {
      const res = await fetchAdmin('/api/admin/discord/register-commands', {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        discordRegisterMessage = { type: 'error', text: data.detail || res.statusText || 'Failed to register commands' };
        return;
      }
      const names = data.registered?.length ? data.registered.join(', ') : 'wallet, collection';
      discordRegisterMessage = { type: 'success', text: `Registered slash commands: ${names}. They will appear in Discord after you set the Interactions Endpoint URL in the Developer Portal.` };
    } catch (e) {
      discordRegisterMessage = { type: 'error', text: e instanceof Error ? e.message : 'Request failed' };
    } finally {
      discordRegistering = false;
    }
  }
</script>

<svelte:head>
  <title>Agent settings · Admin</title>
</svelte:head>

<div class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-lg font-semibold text-neutral-100">Agent settings</h1>
      <p class="text-sm text-neutral-400 mt-0.5">ACA-Py multitenancy agent connection and status</p>
    </div>
    <Button variant="outline" size="sm" class="border-neutral-600 text-neutral-200 hover:bg-neutral-700" onclick={load} disabled={loading}>
      {loading ? 'Loading…' : 'Refresh'}
    </Button>
  </div>

  {#if loading && !settings}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if error}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {:else if settings}
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 p-5">
        <h2 class="text-sm font-medium text-neutral-300 mb-3">Connection</h2>
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between gap-4">
            <dt class="text-neutral-500">Admin URL</dt>
            <dd class="font-mono text-neutral-200 truncate max-w-[200px]" title={settings.admin_url}>
              {settings.admin_url}
            </dd>
          </div>
          <div class="flex justify-between gap-4">
            <dt class="text-neutral-500">URL configured</dt>
            <dd class="text-neutral-200">{settings.admin_url_configured ? 'Yes' : 'No'}</dd>
          </div>
          <div class="flex justify-between gap-4">
            <dt class="text-neutral-500">API key set</dt>
            <dd class="text-neutral-200">{settings.api_key_configured ? 'Yes' : 'No'}</dd>
          </div>
          <div class="flex justify-between gap-4">
            <dt class="text-neutral-500">Innkeeper configured</dt>
            <dd class="text-neutral-200">{settings.innkeeper_configured ? 'Yes' : 'No'}</dd>
          </div>
        </dl>
      </div>

      <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 p-5">
        <h2 class="text-sm font-medium text-neutral-300 mb-3">Status</h2>
        {#if !settings.status.configured}
          <p class="text-sm text-neutral-400">Agent URL not configured. Set ACAPY_ADMIN_URL in the backend environment.</p>
        {:else if settings.status.reachable}
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="text-neutral-500">Reachable</dt>
              <dd class="text-emerald-400">Yes</dd>
            </div>
            {#if settings.status.version}
              <div class="flex justify-between gap-4">
                <dt class="text-neutral-500">Version</dt>
                <dd class="font-mono text-neutral-200">{settings.status.version}</dd>
              </div>
            {/if}
            {#if settings.status.label}
              <div class="flex justify-between gap-4">
                <dt class="text-neutral-500">Label</dt>
                <dd class="text-neutral-200">{settings.status.label}</dd>
              </div>
            {/if}
            {#if settings.status.detail}
              <p class="text-xs text-neutral-500 mt-2">{settings.status.detail}</p>
            {/if}
          </dl>
        {:else}
          <p class="text-sm text-amber-400/90">Not reachable</p>
          {#if settings.status.detail}
            <p class="text-xs text-neutral-500 mt-1">{settings.status.detail}</p>
          {/if}
        {/if}
      </div>
    </div>

    <p class="text-xs text-neutral-500">
      These values come from the backend environment (ACAPY_ADMIN_URL, ACAPY_ADMIN_API_KEY, INNKEEPER_ID, INNKEEPER_KEY).
      Change them in your .env or deployment config; this page is read-only.
    </p>

    <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 p-5">
      <h2 class="text-sm font-medium text-neutral-300 mb-3">Admin API key (optional)</h2>
      <p class="text-xs text-neutral-500 mb-2">Use an API key instead of session cookie for admin requests (e.g. scripts or when cookie is not sent). Set ADMIN_API_KEY in the backend; then paste it here to use it in this browser.</p>
      <div class="flex flex-wrap items-center gap-2">
        <input
          type="password"
          autocomplete="off"
          placeholder="Admin API key"
          bind:value={adminApiKeyInput}
          class="rounded-md border border-neutral-600 bg-neutral-800 px-3 py-1.5 text-sm text-neutral-200 placeholder:text-neutral-500 max-w-xs"
        />
        <Button variant="outline" size="sm" class="border-neutral-600 text-neutral-200 hover:bg-neutral-700" onclick={saveAdminApiKey}>
          Save
        </Button>
        {#if getAdminApiKey()}
          <Button variant="ghost" size="sm" class="text-neutral-400 hover:text-white" onclick={clearAdminApiKey}>Clear</Button>
        {/if}
      </div>
    </div>

    <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 p-5">
      <h2 class="text-sm font-medium text-neutral-300 mb-3">Discord bot (slash commands)</h2>
      {#if !settings.discord_bot_configured}
        <p class="text-sm text-neutral-400">Set DISCORD_BOT_TOKEN and DISCORD_CLIENT_ID in the backend environment to register /wallet and /collection.</p>
      {:else}
        <p class="text-sm text-neutral-400 mb-3">Register slash commands with Discord so /wallet and /collection appear in your server. Do this once (or after changing command names/descriptions).</p>
        <div class="flex flex-wrap gap-2">
          {#if settings.discord_bot_invite_url}
            <a
              href={settings.discord_bot_invite_url}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center rounded-lg border border-neutral-600 bg-neutral-700 px-4 py-2 text-sm font-medium text-neutral-100 no-underline hover:no-underline hover:bg-neutral-600 hover:text-white transition-colors">
              Add bot to server
            </a>
          {/if}
          <Button
            variant="outline"
            size="sm"
            class="border-neutral-600 text-neutral-200 hover:bg-neutral-700"
            onclick={registerDiscordCommands}
            disabled={discordRegistering}
          >
            {discordRegistering ? 'Registering…' : 'Register slash commands'}
          </Button>
        </div>
        {#if settings.discord_bot_invite_url}
          <p class="mt-2 text-xs text-neutral-500">If Discord says “Integration requires code grant”, turn off <strong>Requires OAuth2 Code Grant</strong> in the Developer Portal → your app → OAuth2 → General.</p>
        {/if}
        {#if discordRegisterMessage}
          <p class="mt-3 text-sm {discordRegisterMessage.type === 'success' ? 'text-emerald-400' : 'text-red-400'}">
            {discordRegisterMessage.text}
          </p>
        {/if}
      {/if}
    </div>
  {/if}
</div>
