<script lang="ts">
  import { onMount } from 'svelte';
  import * as Table from '$lib/components/ui/table';
  import { Button } from '$lib/components/ui/button';
  import { fetchAdmin } from '$lib/api';

  type LedgerEntry = {
    id: string;
    event_type: string;
    card_id: string;
    card_name: string;
    card_number: string;
    card_set_name: string;
    to_user_id: string;
    to_username: string;
    from_user_id: string | null;
    from_username: string | null;
    actor_user_id: string | null;
    actor_username: string | null;
    created_at: string;
    payload: unknown;
  };

  function eventLabel(t: string): string {
    if (t === 'card.issued') return 'Card issued';
    if (t === 'card.traded') return 'Card traded';
    return t;
  }

  function eventBadgeClass(t: string): string {
    if (t === 'card.issued') return 'bg-emerald-500/20 text-emerald-400';
    if (t === 'card.traded') return 'bg-amber-500/20 text-amber-400';
    return 'bg-neutral-500/20 text-neutral-400';
  }

  let entries: LedgerEntry[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let filterEventType = $state('');
  let filterUserId = $state('');
  let filterCardId = $state('');

  async function load() {
    loading = true;
    error = '';
    try {
      const params = new URLSearchParams();
      params.set('limit', '200');
      if (filterEventType.trim()) params.set('event_type', filterEventType.trim());
      if (filterUserId.trim()) params.set('user_id', filterUserId.trim());
      if (filterCardId.trim()) params.set('card_id', filterCardId.trim());
      const res = await fetchAdmin(`/api/admin/ledger?${params}`);
      if (!res.ok) throw new Error('Failed to load ledger');
      const data = await res.json();
      entries = data.entries || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      entries = [];
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head>
  <title>Ledger · Admin</title>
</svelte:head>

<div class="space-y-5">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div>
      <h1 class="text-lg font-semibold text-neutral-100">Ledger</h1>
      <p class="text-sm text-neutral-400 mt-0.5">Card issuance and trades</p>
    </div>
  </div>

  <div class="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-700 bg-neutral-800/80 p-3">
    <select
      bind:value={filterEventType}
      class="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-neutral-500">
      <option value="">All events</option>
      <option value="issuance">Issuance</option>
      <option value="trade">Trade</option>
    </select>
    <input
      type="text"
      bind:value={filterUserId}
      placeholder="User ID"
      class="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm placeholder:text-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500 w-48" />
    <input
      type="text"
      bind:value={filterCardId}
      placeholder="Card ID"
      class="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm placeholder:text-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-500 w-48" />
    <Button size="sm" class="h-8 text-xs" onclick={load}>Apply</Button>
  </div>

  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if error}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {:else if entries.length === 0}
    <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 px-4 py-8 text-center text-neutral-400 text-sm">
      No ledger entries yet. Issuances will appear here when you issue cards from the Cards section.
    </div>
  {:else}
    <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 overflow-hidden">
      <div class="overflow-x-auto">
        <Table.Root>
          <Table.Header>
            <Table.Row class="border-b border-neutral-700 hover:bg-transparent">
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Date</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Event</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Card</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">To</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">From</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">By</Table.Head>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#each entries as e}
              <Table.Row class="border-b border-neutral-700/80 last:border-0 hover:bg-neutral-700/40 transition-colors">
                <Table.Cell class="px-4 py-3 text-neutral-300 whitespace-nowrap">{e.created_at}</Table.Cell>
                <Table.Cell class="px-4 py-3">
                  <span class="inline-flex rounded px-1.5 py-0.5 text-xs font-medium {eventBadgeClass(e.event_type)}">
                    {eventLabel(e.event_type)}
                  </span>
                </Table.Cell>
                <Table.Cell class="px-4 py-3">
                  <span class="text-neutral-200">{e.card_name || e.card_id}</span>
                  {#if e.card_number}
                    <span class="text-neutral-500 text-xs ml-1">{e.card_number}</span>
                  {/if}
                  {#if e.card_set_name}
                    <span class="text-neutral-500 text-xs block">{e.card_set_name}</span>
                  {/if}
                </Table.Cell>
                <Table.Cell class="px-4 py-3 text-neutral-300">{e.to_username || e.to_user_id}</Table.Cell>
                <Table.Cell class="px-4 py-3 text-neutral-500">{e.from_username ?? e.from_user_id ?? '—'}</Table.Cell>
                <Table.Cell class="px-4 py-3 text-neutral-400">{e.actor_username ?? '—'}</Table.Cell>
              </Table.Row>
            {/each}
          </Table.Body>
        </Table.Root>
      </div>
    </div>
  {/if}
</div>
