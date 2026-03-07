<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchAdmin } from '$lib/api';

  let stats: { total_users: number; total_sets: number; total_cards: number } | null = $state(null);
  let loading = $state(true);
  let error = $state('');

  onMount(async () => {
    try {
      const res = await fetchAdmin('/api/admin/stats');
      if (!res.ok) throw new Error('Failed to load stats');
      stats = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

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
  {/if}
</div>

<style>
  /* Override global a:hover underline for these card links (app.css sets underline on all links) */
  .admin-overview-card,
  .admin-overview-card:hover {
    text-decoration: none !important;
  }
</style>
