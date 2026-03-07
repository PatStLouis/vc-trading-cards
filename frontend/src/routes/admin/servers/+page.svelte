<script lang="ts">
  import { onMount } from 'svelte';
  import * as Table from '$lib/components/ui/table';
  import { fetchAdmin } from '$lib/api';

  type Guild = {
    id: string;
    name: string;
    icon: string | null;
    owner?: boolean;
    approximate_member_count?: number;
    approximate_presence_count?: number;
    features?: string[];
  };

  let guilds: Guild[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let search = $state('');

  onMount(async () => {
    try {
      const res = await fetchAdmin('/api/admin/discord/guilds');
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || res.statusText || 'Failed to load servers');
      }
      const data = await res.json();
      guilds = data.guilds || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  function iconUrl(g: Guild): string | null {
    if (!g.icon) return null;
    return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
  }

  const filtered = $derived(
    !search.trim()
      ? guilds
      : guilds.filter(
          (g) =>
            (g.name || '').toLowerCase().includes(search.toLowerCase()) ||
            (g.id || '').includes(search)
        )
  );
</script>

<svelte:head>
  <title>Servers · Admin</title>
</svelte:head>

<div class="space-y-5">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-lg font-semibold text-neutral-100">Servers</h1>
      <p class="text-sm text-neutral-400 mt-0.5">Discord servers where the bot has been invited · {guilds.length} total</p>
    </div>
    <input
      type="search"
      placeholder="Search by name or ID…"
      bind:value={search}
      class="w-full sm:w-64 rounded-lg border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
  </div>

  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if error}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {:else}
    <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 overflow-hidden">
      <div class="overflow-x-auto">
        <Table.Root>
          <Table.Header>
            <Table.Row class="border-b border-neutral-700 hover:bg-transparent">
              <Table.Head class="h-10 w-12 px-2 py-3"></Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Server</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Guild ID</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Members</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Online</Table.Head>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#each filtered as g}
              <Table.Row class="border-b border-neutral-700/80 last:border-0 hover:bg-neutral-700/40 transition-colors">
                <Table.Cell class="w-12 px-2 py-3">
                  {#if iconUrl(g)}
                    <img
                      src={iconUrl(g)!}
                      alt=""
                      class="h-8 w-8 rounded-full object-cover bg-neutral-700"
                    />
                  {:else}
                    <div class="h-8 w-8 rounded-full bg-neutral-700 flex items-center justify-center text-neutral-500 text-xs font-medium" title="No icon">
                      {(g.name || '?').charAt(0).toUpperCase()}
                    </div>
                  {/if}
                </Table.Cell>
                <Table.Cell class="px-4 py-3 font-medium text-neutral-100">
                  <a href="/admin/servers/{g.id}" class="text-neutral-100 hover:text-white hover:underline">
                    {g.name || '—'}
                  </a>
                  {#if g.owner}
                    <span class="ml-1.5 text-xs text-amber-400/90" title="Bot owner">(owner)</span>
                  {/if}
                </Table.Cell>
                <Table.Cell class="px-4 py-3 font-mono text-sm text-neutral-400">{g.id}</Table.Cell>
                <Table.Cell class="px-4 py-3 text-sm text-neutral-400">
                  {g.approximate_member_count != null ? g.approximate_member_count.toLocaleString() : '—'}
                </Table.Cell>
                <Table.Cell class="px-4 py-3 text-sm text-neutral-400">
                  {g.approximate_presence_count != null ? g.approximate_presence_count.toLocaleString() : '—'}
                </Table.Cell>
              </Table.Row>
            {/each}
          </Table.Body>
        </Table.Root>
      </div>
      {#if filtered.length === 0}
        <div class="py-12 text-center text-neutral-500 text-sm">
          {search.trim() ? 'No servers match your search.' : 'Bot is not in any servers yet. Invite it via the Discord Developer Portal (OAuth2 → URL Generator).'}
        </div>
      {/if}
    </div>
  {/if}
</div>
