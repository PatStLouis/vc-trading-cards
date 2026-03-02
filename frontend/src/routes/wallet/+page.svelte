<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { Skeleton } from '$lib/components/ui/skeleton';
  import TradingCard from '$lib/components/Card.svelte';
  import { activeCard } from '$lib/stores/activeCard';

  let user: { username: string; wallet_id: string; is_admin?: boolean } | null = $state(null);
  let cards: Array<Record<string, unknown>> = $state([]);
  let loading = $state(true);
  let error = $state('');

  const API = import.meta.env.VITE_API_URL ?? '';

  onMount(async () => {
    try {
      const [meRes, credsRes] = await Promise.all([
        fetch(`${API || ''}/api/me`, { credentials: 'include' }),
        fetch(`${API || ''}/api/wallet/credentials`, { credentials: 'include' })
      ]);
      if (meRes.status === 401) {
        goto('/');
        return;
      }
      if (!meRes.ok) throw new Error('Failed to load user');
      user = await meRes.json();
      if (credsRes.ok) {
        const data = await credsRes.json();
        cards = data.cards || [];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  onMount(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') activeCard.set(null);
    }
    function onClick(e: MouseEvent) {
      const target = e.target as Node;
      const active = document.querySelector('.card.active');
      if (active && active instanceof HTMLElement && !active.contains(target)) activeCard.set(null);
    }
    window.addEventListener('keydown', onKey);
    document.addEventListener('click', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onClick);
    };
  });

  async function logout() {
    await fetch(`${API || ''}/auth/logout`, { method: 'POST', credentials: 'include' });
    goto('/');
  }
</script>

<main class="wallet-page py-6 px-4">
  <Card.Root class="border border-border bg-card text-card-foreground rounded-xl mb-8">
    <Card.Header class="flex flex-row flex-wrap items-center justify-between gap-4 pb-4 border-b border-border">
      <div>
        <Card.Title class="text-xl font-semibold">My collection</Card.Title>
        {#if user}
          <Card.Description class="text-muted-foreground text-sm mt-1">
            @{user.username}
            <span class="font-mono text-xs opacity-80"> · {user.wallet_id?.slice(0, 12)}…</span>
          </Card.Description>
        {/if}
      </div>
      {#if user}
        {#if user.is_admin}
          <Button variant="outline" size="sm" href="/admin">Admin</Button>
        {/if}
        <Button variant="outline" size="sm" onclick={logout}>Log out</Button>
      {/if}
    </Card.Header>
  </Card.Root>

  {#if loading}
    <div class="space-y-4">
      <Skeleton class="h-8 w-48" />
      <div class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
        {#each Array(6) as _}
          <Skeleton class="aspect-[0.718] w-full rounded-[4.55%_/_3.5%] max-w-[280px] mx-auto" />
        {/each}
      </div>
    </div>
  {:else if error}
    <Card.Root class="border border-destructive/50 bg-card text-card-foreground rounded-xl p-6">
      <Card.Content>
        <p class="text-destructive">{error}</p>
      </Card.Content>
    </Card.Root>
  {:else if cards.length === 0}
    <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-8 text-center">
      <Card.Header>
        <Card.Title class="text-lg font-medium">No cards yet</Card.Title>
        <Card.Description class="text-muted-foreground text-sm mt-2">
          Credentials issued to this wallet will appear here as holographic cards.
        </Card.Description>
      </Card.Header>
    </Card.Root>
  {:else}
    <section class="card-grid grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-8 py-4" aria-label="Trading cards">
      {#each cards as card (card.id)}
        <TradingCard
          id={card.id}
          name={String(card.name ?? 'Card')}
          number={String(card.number ?? '')}
          set={String(card.set ?? '')}
          types={Array.isArray(card.types) ? card.types : [card.types].filter(Boolean)}
          subtypes={String(card.subtypes ?? 'trading-cards')}
          supertype={String(card.supertype ?? 'trading-card')}
          rarity={String(card.rarity ?? 'common')}
          img={String(card.image_url ?? card.artwork ?? '')}
        />
      {/each}
    </section>
  {/if}
</main>
