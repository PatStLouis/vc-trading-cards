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

<main class="wallet-page py-8 px-4 md:py-10 relative">
  <div class="wallet-page__bg" aria-hidden="true"></div>

  <div class="relative z-10">
    <!-- Header -->
    <header class="wallet-header mb-8 md:mb-10">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 class="wallet-header__title text-2xl md:text-3xl font-bold tracking-tight">
            My deck
          </h1>
          <p class="wallet-header__tagline text-muted-foreground/80 text-xs mt-0.5">Tritone Cards · The Devil's Interval</p>
          {#if user}
            <p class="wallet-header__meta text-muted-foreground text-sm mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span>@{user.username}</span>
              <span class="wallet-header__wallet-id font-mono text-xs opacity-80" aria-label="Wallet ID">
                {user.wallet_id?.slice(0, 14)}…
              </span>
            </p>
          {/if}
        </div>
        <div class="flex items-center gap-2">
          {#if user}
            {#if user.is_admin}
              <Button variant="outline" size="sm" href="/admin">Admin</Button>
            {/if}
            <Button variant="outline" size="sm" onclick={logout}>Log out</Button>
          {/if}
        </div>
      </div>
      {#if !loading && !error && cards.length >= 0}
        <div class="wallet-header__stat mt-4 inline-flex items-center gap-2 rounded-full bg-primary/10 text-primary px-4 py-1.5 text-sm font-medium">
          <span class="wallet-header__stat-dot" aria-hidden="true"></span>
          {cards.length} {cards.length === 1 ? 'card' : 'cards'}
        </div>
      {/if}
    </header>

    {#if loading}
      <div class="space-y-6">
        <Skeleton class="h-10 w-64 rounded-lg" />
        <div class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-8 py-4">
          {#each Array(6) as _}
            <Skeleton class="aspect-[0.718] w-full rounded-[4.55%_/_3.5%] max-w-[280px] mx-auto" />
          {/each}
        </div>
      </div>
    {:else if error}
      <Card.Root class="wallet-error border border-destructive/50 bg-card/80 text-card-foreground rounded-xl p-8 text-center">
        <Card.Content class="p-0">
          <p class="text-destructive font-medium">{error}</p>
          <p class="text-muted-foreground text-sm mt-2">Check your connection and try again.</p>
        </Card.Content>
      </Card.Root>
    {:else if cards.length === 0}
      <Card.Root class="wallet-empty border border-border/80 bg-card/60 text-card-foreground rounded-2xl p-12 md:p-16 text-center backdrop-blur-sm">
        <div class="wallet-empty__icon mx-auto mb-6 w-20 h-20 rounded-2xl bg-primary/15 flex items-center justify-center" aria-hidden="true">
          <svg class="w-10 h-10 text-primary/80" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <Card.Header class="p-0">
        <Card.Title class="text-xl font-semibold">No cards yet</Card.Title>
        <Card.Description class="text-muted-foreground mt-3 max-w-md mx-auto leading-relaxed">
          Credentials issued to this wallet will show up here as holographic Tritone cards. Get your first credential to start your deck.
        </Card.Description>
        </Card.Header>
      </Card.Root>
    {:else}
      <section class="card-grid grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-8 py-4" aria-label="Collectible cards">
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
  </div>
</main>

<style>
  .wallet-page {
    font-family: var(--font-heading);
  }

  .wallet-page__bg {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 70% 40% at 50% 0%, oklch(0.22 0.06 264 / 0.4), transparent 60%);
    pointer-events: none;
  }

  .wallet-header__title {
    font-family: var(--font-heading);
  }

  .wallet-header__wallet-id {
    font-family: var(--font-mono);
  }

  .wallet-header__stat-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.8;
  }

  .wallet-empty__icon {
    font-family: var(--font-heading);
  }
</style>
