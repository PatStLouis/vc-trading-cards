<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { Skeleton } from '$lib/components/ui/skeleton';
  import TradingCard from '$lib/components/Card.svelte';
  import AppHeader from '$lib/components/AppHeader.svelte';
  import { activeCard } from '$lib/stores/activeCard';
  import { fetchApi, apiUrl } from '$lib/api';
  import { page } from '$app/stores';

  type SetInfo = { id: string; name: string; card_back_path?: string };
  let user: { username: string; wallet_id: string; is_admin?: boolean; avatar_url?: string | null; pending_issued_count?: number } | null = $state(null);
  let cards: Array<Record<string, unknown>> = $state([]);
  let sets: SetInfo[] = $state([]);
  let loading = $state(true);
  let error = $state('');

  let dismissAdminNotice = $state(false);

  const API = apiUrl();
  const showAdminRequiredNotice = $derived(
    !dismissAdminNotice &&
    $page.url.searchParams.get('admin_required') === '1' &&
    user !== null &&
    !user.is_admin
  );

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = (API || '').replace(/\/$/, '');
    return path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }
  function backUrlForSetName(setName: string): string {
    const s = sets.find((x) => (x.name || '').trim() === (setName || '').trim());
    if (s?.card_back_path) return imageUrl(s.card_back_path);
    return '/card-back.svg';
  }
  /** Card image URL: use as-is if full URL, else prepend uploads base (for admin-issued cards). */
  function cardImageUrl(card: Record<string, unknown>): string {
    const u = String(card?.image_url ?? card?.artwork ?? '');
    if (!u) return '';
    if (u.startsWith('http')) return u;
    return imageUrl(u);
  }

  onMount(async () => {
    try {
      const raw = localStorage.getItem(GRID_SETS_KEY);
      if (raw) {
        const arr = JSON.parse(raw) as string[];
        if (Array.isArray(arr)) gridModeForSet = new Set(arr);
      }
    } catch (_) {}
    try {
      const [meRes, credsRes, setsRes] = await Promise.all([
        fetchApi('/api/me', { auth: true }),
        fetchApi('/api/wallet/cards', { auth: true }),
        fetchApi('/api/public/sets')
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
      if (setsRes.ok) {
        const data = await setsRes.json();
        sets = data.sets || [];
      }
      // Mark issued cards as seen so notification badge clears
      try {
        await fetchApi('/api/wallet/seen-issued', { method: 'POST', auth: true });
        const meAgain = await fetchApi('/api/me', { auth: true });
        if (meAgain.ok) user = await meAgain.json();
      } catch (_) {}
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

  // When a card is expanded, lock body scroll and prevent touch from scrolling the background
  $effect(() => {
    const active = $activeCard;
    if (active) {
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      const preventTouchScroll = (e: TouchEvent) => e.preventDefault();
      document.addEventListener('touchmove', preventTouchScroll, { passive: false });
      return () => {
        document.body.style.overflow = prevOverflow;
        document.removeEventListener('touchmove', preventTouchScroll);
      };
    }
  });

  /** Unique key for collapsing duplicates (same set + name + number = same card). */
  function cardGroupKey(card: Record<string, unknown>): string {
    const set = String(card.set ?? '').trim();
    const name = String(card.name ?? '').trim();
    const number = String(card.number ?? '').trim();
    return `${set}\0${name}\0${number}`;
  }

  // Group cards by set; within each set collapse duplicates and count
  const cardsBySet = $derived.by(() => {
    const setToGroups = new Map<string, Map<string, Array<Record<string, unknown>>>>();
    const setOrder: string[] = [];
    for (const card of cards) {
      const set = String(card.set ?? 'Other').trim() || 'Other';
      if (!setToGroups.has(set)) {
        setToGroups.set(set, new Map());
        setOrder.push(set);
      }
      const groupMap = setToGroups.get(set)!;
      const key = cardGroupKey(card);
      if (!groupMap.has(key)) groupMap.set(key, []);
      groupMap.get(key)!.push(card);
    }
    return setOrder.map((set) => {
      const groupMap = setToGroups.get(set)!;
      const items = Array.from(groupMap.values()).map((arr) => ({
        card: arr[0] as Record<string, unknown>,
        count: arr.length,
      }));
      return { set, items };
    });
  });

  const totalCardCount = $derived(cards.length);

  // Per-set view mode: sets in this Set show as grid; others show as horizontal row (persisted)
  const GRID_SETS_KEY = 'wallet-grid-sets';
  let gridModeForSet = $state<Set<string>>(new Set());

  function toggleSetView(setName: string) {
    gridModeForSet = new Set(gridModeForSet);
    if (gridModeForSet.has(setName)) gridModeForSet.delete(setName);
    else gridModeForSet.add(setName);
    try {
      localStorage.setItem(GRID_SETS_KEY, JSON.stringify([...gridModeForSet]));
    } catch (_) {}
  }
</script>

<main class="app-page py-8 px-4 md:py-10 relative">
  <div class="app-page__bg" aria-hidden="true"></div>
  <div class="texture-overlay" aria-hidden="true"></div>

  <div class="relative z-10">
    <AppHeader title="My deck" {user} showExploreButton={false} />
    {#if showAdminRequiredNotice}
        <div class="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 flex items-start gap-3">
          <p class="text-amber-200 text-sm flex-1">
            Admin access is only available to users listed in <code class="font-mono text-xs bg-black/20 px-1 rounded">ADMIN_DISCORD_IDS</code> in the backend <code class="font-mono text-xs bg-black/20 px-1 rounded">.env</code>. Add your Discord user ID there (comma-separated for multiple admins), then restart the backend and log in again.
          </p>
          <Button variant="ghost" size="sm" class="shrink-0 text-amber-300 hover:text-amber-200" onclick={() => { dismissAdminNotice = true; goto('/wallet', { replaceState: true }); }} aria-label="Dismiss">×</Button>
        </div>
      {/if}
    {#if !loading && !error && cards.length >= 0}
      <div class="wallet-header__stat mt-4 flex flex-wrap items-center gap-2">
        <div class="inline-flex items-center gap-2 rounded-full bg-primary/10 text-primary px-4 py-1.5 text-sm font-medium">
          <span class="wallet-header__stat-dot" aria-hidden="true"></span>
          {totalCardCount} {totalCardCount === 1 ? 'card' : 'cards'}
        </div>
      </div>
    {/if}

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
          Collect cards to build your deck. Get your first card to get started.
        </Card.Description>
        </Card.Header>
      </Card.Root>
    {:else}
      <div class="wallet-rows space-y-8 overflow-visible" aria-label="Collectible cards by set">
        {#each cardsBySet as { set: setName, items: setItems }}
          {@const isGrid = gridModeForSet.has(setName)}
          <section class="wallet-set overflow-visible" aria-label="{setName}" class:wallet-set--grid={isGrid}>
            <div class="wallet-set__header flex items-center justify-between gap-2 mb-3 px-1">
              <h2 class="wallet-row__title font-display text-lg font-semibold text-foreground tracking-wide">{setName}</h2>
              <button
                type="button"
                class="wallet-set__toggle rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                aria-label={isGrid ? 'Show as scrolling row' : 'Show as grid'}
                title={isGrid ? 'Row view' : 'Grid view'}
                onclick={() => toggleSetView(setName)}
              >
                {#if isGrid}
                  <!-- Row icon: horizontal scroll -->
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                {:else}
                  <!-- Grid icon -->
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                {/if}
              </button>
            </div>
            <div class="wallet-set__content transition-[opacity,transform] duration-300 ease-out">
              {#if isGrid}
                <div class="wallet-set__grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                  {#each setItems as { card, count } (cardGroupKey(card))}
                    <div class="wallet-set__grid-card flex justify-center relative">
                      <TradingCard
                        noTilt={true}
                        id={card.id}
                        name={String(card.name ?? 'Card')}
                        number={String(card.number ?? '')}
                        set={String(card.set ?? '')}
                        types={Array.isArray(card.types) ? card.types : [card.types].filter(Boolean)}
                        subtypes={String(card.subtypes ?? 'trading-cards')}
                        supertype={String(card.supertype ?? 'trading-card')}
                        rarity={String(card.rarity ?? 'common')}
                        img={cardImageUrl(card)}
                        back={backUrlForSetName(String(card.set ?? ''))}
                      />
                      {#if count > 1}
                        <span class="wallet-card-count absolute top-1 left-1/2 -translate-x-1/2 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-semibold text-white tabular-nums" aria-label="{count} copies">×{count}</span>
                      {/if}
                    </div>
                  {/each}
                </div>
              {:else}
                <div class="wallet-row__scroll flex gap-6 overflow-x-auto overflow-y-visible pb-2 -mx-1 px-1">
                  {#each setItems as { card, count } (cardGroupKey(card))}
                    <div class="wallet-row__card flex-shrink-0 w-[min(240px,68vw)] max-w-[240px] relative">
                      <TradingCard
                        id={card.id}
                        name={String(card.name ?? 'Card')}
                        number={String(card.number ?? '')}
                        set={String(card.set ?? '')}
                        types={Array.isArray(card.types) ? card.types : [card.types].filter(Boolean)}
                        subtypes={String(card.subtypes ?? 'trading-cards')}
                        supertype={String(card.supertype ?? 'trading-card')}
                        rarity={String(card.rarity ?? 'common')}
                        img={cardImageUrl(card)}
                        back={backUrlForSetName(String(card.set ?? ''))}
                      />
                      {#if count > 1}
                        <span class="wallet-card-count absolute top-1 left-1/2 -translate-x-1/2 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-semibold text-white tabular-nums" aria-label="{count} copies">×{count}</span>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </section>
        {/each}
      </div>
    {/if}
  </div>
</main>

<style>
  .wallet-header__stat-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.8;
  }

  .wallet-card-count {
    z-index: 1;
  }

  .wallet-empty__icon {
    font-family: var(--font-heading);
  }

  .wallet-row__scroll {
    scroll-snap-type: x proximity;
    -webkit-overflow-scrolling: touch;
    scroll-behavior: smooth;
  }
  .wallet-row__scroll::-webkit-scrollbar {
    height: 6px;
  }
  .wallet-row__scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .wallet-row__scroll::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 3px;
  }
  .wallet-row__scroll::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.3);
  }
  .wallet-row__card {
    scroll-snap-align: start;
  }

  /* Grid: limit card size so they don’t grow too large */
  .wallet-set__grid-card {
    max-width: 140px;
    margin-left: auto;
    margin-right: auto;
  }
  @media (min-width: 640px) {
    .wallet-set__grid-card { max-width: 150px; }
  }
  @media (min-width: 768px) {
    .wallet-set__grid-card { max-width: 160px; }
  }
  @media (min-width: 1024px) {
    .wallet-set__grid-card { max-width: 150px; }
  }
</style>
