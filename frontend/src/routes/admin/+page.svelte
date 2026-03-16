<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchAdmin } from '$lib/api';

  let stats: { total_users: number; total_sets: number; total_cards: number } | null = $state(null);
  let loading = $state(true);
  let error = $state('');

  let syncSourceUrl = $state('http://localhost:8000');
  let syncForce = $state(false);
  let syncLoading = $state(false);
  let syncResult: { synced: number; skipped: number; errors: { card_id: string; image_path: string; error: string }[] } | null = $state(null);
  let syncError = $state('');

  let pushPullForce = $state(false);
  let pushLoading = $state(false);
  let pushResult: { pushed: number; skipped: number; errors: { card_id: string; image_path: string; error: string }[] } | null = $state(null);
  let pushError = $state('');
  let pullLoading = $state(false);
  let pullResult: { pulled: number; skipped: number; errors: { card_id: string; image_path: string; error: string }[] } | null = $state(null);
  let pullError = $state('');

  onMount(async () => {
    try {
      const res = await fetchAdmin('/api/admin/stats');
      if (res.status === 401) {
        error = 'Not logged in or session expired. Log in again from the main page. If you use a separate frontend/backend URL, set VITE_API_URL and FRONTEND_URL. On a single domain, set COOKIE_DOMAIN (e.g. .tritone.cards) if you use www and apex, or ensure BACKEND_URL matches the host users visit.';
        return;
      }
      if (!res.ok) throw new Error('Failed to load stats');
      stats = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  async function runSync() {
    syncError = '';
    syncResult = null;
    syncLoading = true;
    try {
      const res = await fetchAdmin('/api/admin/sync-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: syncSourceUrl.trim() || undefined, force: syncForce }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        syncError = data.detail || res.statusText || 'Sync failed';
        return;
      }
      syncResult = data;
    } catch (e) {
      syncError = e instanceof Error ? e.message : 'Sync failed';
    } finally {
      syncLoading = false;
    }
  }

  async function runPushToDb() {
    pushError = '';
    pushResult = null;
    pushLoading = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 min for large syncs
    try {
      const res = await fetchAdmin('/api/admin/push-images-to-db', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: pushPullForce }),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        pushError = data.detail || res.statusText || 'Push failed';
        return;
      }
      pushResult = data;
    } catch (e) {
      pushError = e instanceof Error ? e.message : 'Push failed';
    } finally {
      clearTimeout(timeout);
      pushLoading = false;
    }
  }

  async function runPullFromDb() {
    pullError = '';
    pullResult = null;
    pullLoading = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 min for large syncs
    try {
      const res = await fetchAdmin('/api/admin/pull-images-from-db', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: pushPullForce }),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        pullError = data.detail || res.statusText || 'Pull failed';
        return;
      }
      pullResult = data;
    } catch (e) {
      pullError = e instanceof Error ? e.message : 'Pull failed';
    } finally {
      clearTimeout(timeout);
      pullLoading = false;
    }
  }

  const links = $derived([
    { href: '/admin/users', label: 'Users', value: stats?.total_users ?? 0, desc: 'Collectors' },
    { href: '/admin/manage-cards', label: 'Cards', value: stats?.total_cards ?? 0, desc: `Across ${stats?.total_sets ?? 0} sets` },
  ]);
</script>

<div class="space-y-6">
  <div>
    <h1 class="text-lg font-semibold text-neutral-100">Overview</h1>
    <p class="text-sm text-neutral-400 mt-0.5">Stats and quick actions</p>
  </div>

  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if error}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each links as link}
        <a
          href={link.href}
          class="admin-overview-card group block rounded-xl border border-neutral-700 bg-neutral-800/80 p-5 no-underline hover:no-underline transition-all duration-200 ease-out hover:border-neutral-500 hover:bg-neutral-800 hover:shadow-lg hover:shadow-black/20 hover:-translate-y-0.5 hover:scale-[1.01]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <span class="font-medium text-neutral-100 group-hover:text-white transition-colors">{link.label}</span>
              <p class="text-sm text-neutral-400 mt-0.5 group-hover:text-neutral-300 transition-colors">{link.desc}</p>
            </div>
            <span class="tabular-nums text-2xl font-semibold text-neutral-100 group-hover:text-white transition-colors">{link.value}</span>
          </div>
          <span class="mt-3 inline-block text-sm text-neutral-400 group-hover:text-white group-hover:translate-x-0.5 transition-all duration-200">View →</span>
        </a>
      {/each}
    </div>

    <div class="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
      <p class="text-sm font-medium text-neutral-200">Quick actions</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <a href="/admin/users" class="rounded-lg bg-neutral-600 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-500">View users</a>
        <a href="/admin/manage-cards" class="rounded-lg border border-neutral-600 bg-neutral-800 px-4 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-700">Manage cards</a>
        <a href="/wallet" class="rounded-lg border border-neutral-600 bg-neutral-800 px-4 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-700">Open my deck</a>
      </div>
    </div>

    <div class="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
      <p class="text-sm font-medium text-neutral-200">Sync via DB</p>
      <p class="text-xs text-neutral-500 mt-0.5">Shared DB: push local images into the DB, then pull from DB on the other instance to write files.</p>
      <div class="mt-3 flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-2 shrink-0">
          <input type="checkbox" bind:checked={pushPullForce} class="rounded border-neutral-600" />
          <span class="text-sm text-neutral-400">Force overwrite</span>
        </label>
        <button
          type="button"
          onclick={runPushToDb}
          disabled={pushLoading || pullLoading}
          class="rounded-lg bg-neutral-600 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pushLoading ? 'Pushing…' : 'Push to DB'}
        </button>
        <button
          type="button"
          onclick={runPullFromDb}
          disabled={pushLoading || pullLoading}
          class="rounded-lg border border-neutral-600 bg-neutral-800 px-4 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pullLoading ? 'Pulling…' : 'Pull from DB'}
        </button>
      </div>
      {#if pushError}
        <p class="mt-3 text-sm text-red-400">Push: {pushError}</p>
      {/if}
      {#if pushResult}
        <p class="mt-3 text-sm text-neutral-300">
          Push — stored in DB: {pushResult.pushed}, skipped: {pushResult.skipped}
          {#if pushResult.errors.length > 0}
            <span class="text-amber-400">; {pushResult.errors.length} error(s)</span>
          {/if}
        </p>
        {#if pushResult.errors.length > 0}
          <ul class="mt-1 text-xs text-neutral-500 list-disc list-inside max-h-16 overflow-y-auto">
            {#each pushResult.errors as err}
              <li>{err.image_path}: {err.error}</li>
            {/each}
          </ul>
        {/if}
      {/if}
      {#if pullError}
        <p class="mt-3 text-sm text-red-400">Pull: {pullError}</p>
      {/if}
      {#if pullResult}
        <p class="mt-3 text-sm text-neutral-300">
          Pull — written to disk: {pullResult.pulled}, skipped: {pullResult.skipped}
          {#if pullResult.errors.length > 0}
            <span class="text-amber-400">; {pullResult.errors.length} error(s)</span>
          {/if}
        </p>
        {#if pullResult.errors.length > 0}
          <ul class="mt-1 text-xs text-neutral-500 list-disc list-inside max-h-16 overflow-y-auto">
            {#each pullResult.errors as err}
              <li>{err.image_path}: {err.error}</li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>

    <div class="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
      <p class="text-sm font-medium text-neutral-200">Sync from URL</p>
      <p class="text-xs text-neutral-500 mt-0.5">Pull images from another instance (e.g. local via tunnel) when DB is shared but files are only on the source.</p>
      <div class="mt-3 flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1 min-w-0 flex-1 sm:max-w-xs">
          <span class="text-xs text-neutral-400">Source URL</span>
          <input
            type="url"
            bind:value={syncSourceUrl}
            placeholder="http://localhost:8000"
            class="rounded-lg border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-neutral-500 focus:outline-none"
          />
        </label>
        <label class="flex items-center gap-2 shrink-0">
          <input type="checkbox" bind:checked={syncForce} class="rounded border-neutral-600" />
          <span class="text-sm text-neutral-400">Force re-download</span>
        </label>
        <button
          type="button"
          onclick={runSync}
          disabled={syncLoading}
          class="rounded-lg bg-neutral-600 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {syncLoading ? 'Syncing…' : 'Sync from source'}
        </button>
      </div>
      {#if syncError}
        <p class="mt-3 text-sm text-red-400">{syncError}</p>
      {/if}
      {#if syncResult}
        <p class="mt-3 text-sm text-neutral-300">
          Synced: {syncResult.synced}, skipped (already present): {syncResult.skipped}
          {#if syncResult.errors.length > 0}
            <span class="text-amber-400">; {syncResult.errors.length} error(s)</span>
          {/if}
        </p>
        {#if syncResult.errors.length > 0}
          <ul class="mt-1 text-xs text-neutral-500 list-disc list-inside max-h-24 overflow-y-auto">
            {#each syncResult.errors as err}
              <li>{err.image_path}: {err.error}</li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  /* Override global a:hover underline for these card links (app.css sets underline on all links) */
  .admin-overview-card,
  .admin-overview-card:hover {
    text-decoration: none !important;
  }
</style>
