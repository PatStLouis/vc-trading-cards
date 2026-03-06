<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';

  type AgentSettings = {
    admin_url: string;
    admin_url_configured: boolean;
    api_key_configured: boolean;
    innkeeper_configured: boolean;
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

  const API = import.meta.env.VITE_API_URL ?? '';

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetch(`${API}/api/admin/agent/settings`, { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load agent settings');
      settings = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      settings = null;
    } finally {
      loading = false;
    }
  }

  onMount(load);
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
  {/if}
</div>
