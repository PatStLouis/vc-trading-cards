<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { Skeleton } from '$lib/components/ui/skeleton';
  import TradingCard from '$lib/components/Card.svelte';
  import AppIcon from '$lib/components/AppIcon.svelte';
  import { activeCard } from '$lib/stores/activeCard';
  import { fetchApi, apiUrl } from '$lib/api';
  import { page } from '$app/stores';

  type SetInfo = { id: string; name: string; card_back_path?: string };
  let user: { username: string; wallet_id: string; is_admin?: boolean } | null = $state(null);
  let cards: Array<Record<string, unknown>> = $state([]);
  let sets: SetInfo[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let syncing = $state(false);
  let syncMessage = $state('');

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

  async function logout() {
    await fetchApi('/auth/logout', { method: 'POST', auth: true });
    goto('/');
  }

  async function syncCollection() {
    if (!user || syncing) return;
    syncing = true;
    syncMessage = '';
    try {
      const res = await fetchApi('/api/wallet/cards/sync', { method: 'POST', auth: true });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        syncMessage = data.message || 'Collection synced. You now appear in Explore.';
      } else {
        syncMessage = data.detail || 'Sync failed.';
      }
    } catch {
      syncMessage = 'Sync failed.';
    } finally {
      syncing = false;
    }
  }

  // Group cards by set for row layout; preserve order of first appearance
  const cardsBySet = $derived.by(() => {
    const groups = new Map<string, Array<Record<string, unknown>>>();
    const order: string[] = [];
    for (const card of cards) {
      const set = String(card.set ?? 'Other').trim() || 'Other';
      if (!groups.has(set)) {
        groups.set(set, []);
        order.push(set);
      }
      groups.get(set)!.push(card);
    }
    return order.map((set) => ({ set, items: groups.get(set)! }));
  });
</script>

<main class="wallet-page py-8 px-4 md:py-10 relative">
  <div class="wallet-page__bg" aria-hidden="true"></div>

  <div class="relative z-10">
    <!-- Header -->
    <header class="wallet-header mb-8 md:mb-10">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div class="flex items-center gap-3">
          <AppIcon size="lg" class="rounded-xl" />
          <div>
            <h1 class="wallet-header__title font-display text-3xl md:text-4xl tracking-tight uppercase">
              My deck
            </h1>
          <p class="wallet-header__tagline text-muted-foreground/80 text-xs mt-0.5">Your deck · Exclusive band collectibles</p>
          {#if user}
            <p class="wallet-header__meta text-muted-foreground text-sm mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span>@{user.username}</span>
              <span class="wallet-header__wallet-id font-mono text-xs opacity-80" aria-label="Wallet ID">
                {user.wallet_id?.slice(0, 14)}…
              </span>
            </p>
          {/if}
          </div>
        </div>
        <div class="flex items-center gap-2">
          {#if user}
            <Button variant="ghost" size="sm" href="/search">Explore</Button>
            <Button variant="outline" size="sm" href="/wallet/profile">Profile</Button>
            <Button variant="outline" size="sm" href="/wallet/account">Account</Button>
            {#if user.is_admin}
              <Button variant="outline" size="sm" href="/admin">Admin</Button>
            {/if}
            <Button variant="outline" size="sm" onclick={logout}>Log out</Button>
          {/if}
        </div>
      </div>
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
            {cards.length} {cards.length === 1 ? 'card' : 'cards'}
          </div>
          <Button variant="outline" size="sm" class="rounded-full" onclick={syncCollection} disabled={syncing || cards.length === 0}>
            {syncing ? 'Syncing…' : 'Sync to Explore'}
          </Button>
          {#if syncMessage}
            <span class="text-xs text-muted-foreground">{syncMessage}</span>
          {/if}
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
          Cards you collect will show up here as holographic Tritone cards. Get your first card to start building your deck.
        </Card.Description>
        </Card.Header>
      </Card.Root>
    {:else}
      <div class="wallet-rows space-y-8" aria-label="Collectible cards by set">
        {#each cardsBySet as { set: setName, items: setCards }}
          <section class="wallet-row" aria-label="{setName}">
            <h2 class="wallet-row__title text-lg font-semibold text-foreground mb-3 px-1">{setName}</h2>
            <div class="wallet-row__scroll flex gap-6 overflow-x-auto overflow-y-hidden pb-2 -mx-1 px-1">
              {#each setCards as card (card.id)}
                <div class="wallet-row__card flex-shrink-0 w-[min(280px,75vw)] max-w-[280px]">
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
                </div>
              {/each}
            </div>
          </section>
        {/each}
      </div>
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
      radial-gradient(ellipse 70% 40% at 50% 0%, oklch(0.22 0.08 25 / 0.45), transparent 60%);
    pointer-events: none;
  }

  .wallet-header__title {
    font-family: var(--font-display);
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

  .wallet-row__scroll {
    scroll-snap-type: x proximity;
    -webkit-overflow-scrolling: touch;
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
</style>
