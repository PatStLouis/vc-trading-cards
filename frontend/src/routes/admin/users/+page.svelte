<script lang="ts">
  import { onMount } from 'svelte';
  import * as Table from '$lib/components/ui/table';
  import { Button } from '$lib/components/ui/button';

  type UserRow = { discord_sub: string; discord_username: string; wallet_id: string; created_at: string | null };

  let users: UserRow[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let search = $state('');

  const API = import.meta.env.VITE_API_URL ?? '';

  onMount(async () => {
    try {
      const res = await fetch(`${API}/api/admin/users`, { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load users');
      const data = await res.json();
      users = data.users || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  function copyWalletId(walletId: string) {
    navigator.clipboard.writeText(walletId).then(() => {
      copiedId = walletId;
      setTimeout(() => (copiedId = ''), 1500);
    });
  }
  let copiedId = $state('');

  const filtered = $derived(
    !search.trim()
      ? users
      : users.filter(
          (u) =>
            (u.discord_username || '').toLowerCase().includes(search.toLowerCase()) ||
            (u.discord_sub || '').includes(search) ||
            (u.wallet_id || '').toLowerCase().includes(search.toLowerCase())
        )
  );
</script>

<div class="space-y-5">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-lg font-semibold text-neutral-100">Users</h1>
      <p class="text-sm text-neutral-400 mt-0.5">Discord collectors · {users.length} total</p>
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
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Username</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Discord ID</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Wallet ID</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-right text-xs font-medium text-neutral-400 uppercase tracking-wider">Created</Table.Head>
              <Table.Head class="h-10 w-12 px-2 py-3"></Table.Head>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#each filtered as u}
              <Table.Row class="border-b border-neutral-700/80 last:border-0 hover:bg-neutral-700/40 transition-colors">
                <Table.Cell class="px-4 py-3 font-medium text-neutral-100">{u.discord_username || '—'}</Table.Cell>
                <Table.Cell class="px-4 py-3 font-mono text-sm text-neutral-400">{u.discord_sub}</Table.Cell>
                <Table.Cell class="max-w-[200px] truncate px-4 py-3 font-mono text-sm text-neutral-400" title={u.wallet_id}>
                  {u.wallet_id}
                </Table.Cell>
                <Table.Cell class="px-4 py-3 text-right text-sm text-neutral-400 whitespace-nowrap">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString(undefined, { dateStyle: 'short' }) : '—'}
                </Table.Cell>
                <Table.Cell class="px-2 py-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-8 w-8 p-0 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700"
                    title="Copy wallet ID"
                    onclick={() => copyWalletId(u.wallet_id)}>
                    {#if copiedId === u.wallet_id}
                      <span class="text-xs text-emerald-400">Copied</span>
                    {:else}
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                      </svg>
                    {/if}
                  </Button>
                </Table.Cell>
              </Table.Row>
            {/each}
          </Table.Body>
        </Table.Root>
      </div>
      {#if filtered.length === 0}
        <div class="py-12 text-center text-neutral-500 text-sm">
          {search.trim() ? 'No users match your search.' : 'No users yet.'}
        </div>
      {/if}
    </div>
  {/if}
</div>
