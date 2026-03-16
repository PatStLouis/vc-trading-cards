<script lang="ts">
  import { onMount } from 'svelte';
  import * as Table from '$lib/components/ui/table';
  import AppHeader from '$lib/components/AppHeader.svelte';
  import { apiUrl, fetchApi } from '$lib/api';

  const API = apiUrl();

  type LedgerEntry = {
    id: string;
    event_type: string;
    card_id: string;
    card_name: string;
    card_number: string;
    card_set_name: string;
    card_image_path: string;
    to_user_id: string;
    to_username: string;
    from_user_id: string | null;
    from_username: string | null;
    actor_user_id: string | null;
    actor_username: string | null;
    created_at: string;
    issued_card_id: string | null;
    payload: unknown;
  };

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = API.replace(/\/$/, '');
    return path.startsWith('http') ? path : path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }

  function eventLabel(t: string): string {
    if (t === 'card.issued') return 'Issued';
    if (t === 'card.traded') return 'Traded';
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
  let me: { username?: string; avatar_url?: string | null; is_admin?: boolean } | null = $state(null);

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetchApi('/api/public/ledger', { auth: false });
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

  onMount(async () => {
    try {
      const r = await fetchApi('/api/me', { auth: true });
      if (r.ok) me = await r.json();
    } catch {
      me = null;
    }
    await load();
  });
</script>

<svelte:head>
  <title>Ledger · Brutality Cards</title>
</svelte:head>

<AppHeader title="Ledger" user={me} showExploreButton={true} showHomeLink={true} />
<div class="space-y-5">
  <p class="text-sm text-muted-foreground">Card issuances and trades. Data is derived from the public ledger.</p>

  {#if loading}
    <div class="py-12 text-center text-muted-foreground text-sm">Loading…</div>
  {:else if error}
    <div class="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-destructive text-sm">{error}</div>
  {:else if entries.length === 0}
    <div class="rounded-xl border border-border bg-card px-4 py-8 text-center text-muted-foreground text-sm">
      No ledger entries yet.
    </div>
  {:else}
    <div class="rounded-xl border border-border bg-card overflow-hidden">
      <div class="overflow-x-auto">
        <Table.Root>
          <Table.Header>
            <Table.Row class="border-b border-border hover:bg-transparent">
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Card</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Action</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">To</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">From</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Date</Table.Head>
              <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">ID</Table.Head>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {#each entries as e}
              <Table.Row class="border-b border-border/80 last:border-0 hover:bg-muted/40 transition-colors">
                <Table.Cell class="px-4 py-2">
                  <div class="flex items-center gap-3">
                    {#if e.card_image_path}
                      <img
                        src={imageUrl(e.card_image_path)}
                        alt={e.card_name || e.card_id}
                        class="h-10 w-7 object-contain rounded border border-border shrink-0"
                      />
                    {:else}
                      <span class="h-10 w-7 rounded border border-border bg-muted shrink-0 flex items-center justify-center text-[10px] text-muted-foreground">—</span>
                    {/if}
                    <span class="text-foreground text-sm">{e.card_name || e.card_id}</span>
                    {#if e.card_number}
                      <span class="text-muted-foreground text-xs">{e.card_number}</span>
                    {/if}
                  </div>
                </Table.Cell>
                <Table.Cell class="px-4 py-2">
                  <span class="inline-flex rounded px-1.5 py-0.5 text-xs font-medium {eventBadgeClass(e.event_type)}">
                    {eventLabel(e.event_type)}
                  </span>
                </Table.Cell>
                <Table.Cell class="px-4 py-2 text-foreground text-sm">{e.to_username || e.to_user_id}</Table.Cell>
                <Table.Cell class="px-4 py-2 text-muted-foreground text-sm">{e.from_username ?? e.from_user_id ?? '—'}</Table.Cell>
                <Table.Cell class="px-4 py-2 text-muted-foreground text-sm whitespace-nowrap">{e.created_at}</Table.Cell>
                <Table.Cell class="px-4 py-2">
                  {#if e.issued_card_id}
                    <code class="text-xs text-muted-foreground font-mono truncate max-w-[8rem] block" title={e.issued_card_id}>{e.issued_card_id.slice(0, 8)}…</code>
                  {:else}
                    <span class="text-muted-foreground text-xs">—</span>
                  {/if}
                </Table.Cell>
              </Table.Row>
            {/each}
          </Table.Body>
        </Table.Root>
      </div>
    </div>
  {/if}
</div>
