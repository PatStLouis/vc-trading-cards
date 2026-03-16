<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import TradingCard from '$lib/components/Card.svelte';
  import AppHeader from '$lib/components/AppHeader.svelte';
  import { apiUrl, fetchApi } from '$lib/api';

  const API = apiUrl();

  type Set = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string };
  type Card = {
    id: string; set_id: string; name: string; number: string; rarity: string; set_name: string;
    image_path: string; types: string[]; subtypes: string; supertype: string; card_back_path?: string;
  };
  type User = { user_id: string; username: string; poser_username?: string | null; collection_count: number };

  let me: { username?: string; avatar_url?: string | null; is_admin?: boolean; pending_issued_count?: number } | null = $state(null);
  let tab: 'catalog' | 'users' = $state('catalog');
  let sets: Set[] = $state([]);
  let setsLoading = $state(false);
  let selectedSet: Set | null = $state(null);
  let setCards: Card[] = $state([]);
  let setCardsLoading = $state(false);

  let userQuery = $state('');
  let userSearchResults: User[] = $state([]);
  let usersLoading = $state(false);
  let selectedUser: User | null = $state(null);
  let userCollection: Card[] = $state([]);
  let userCollectionLoading = $state(false);

  let selectedCard: Card | null = $state(null);
  let cardOwners: { user_id?: string; discord_sub?: string; username: string }[] = $state([]);
  let cardOwnersLoading = $state(false);

  // Grid/row view (consistent with My deck): per-set and user collection, persisted
  const CATALOGUE_GRID_SETS_KEY = 'catalogue-grid-sets';
  const CATALOGUE_USER_GRID_KEY = 'catalogue-user-grid';
  let gridModeForSetId = $state<Set<string>>(new Set());
  let userCollectionGrid = $state(true);

  function toggleSetViewMode(setId: string) {
    gridModeForSetId = new Set(gridModeForSetId);
    if (gridModeForSetId.has(setId)) gridModeForSetId.delete(setId);
    else gridModeForSetId.add(setId);
    try {
      localStorage.setItem(CATALOGUE_GRID_SETS_KEY, JSON.stringify([...gridModeForSetId]));
    } catch (_) {}
  }

  function toggleUserCollectionView() {
    userCollectionGrid = !userCollectionGrid;
    try {
      localStorage.setItem(CATALOGUE_USER_GRID_KEY, String(userCollectionGrid));
    } catch (_) {}
  }

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = API.replace(/\/$/, '');
    return path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }
  function setBackUrl(set: Set): string {
    if (set?.card_back_path) return imageUrl(set.card_back_path);
    return '/card-back.svg';
  }
  function cardBackUrl(card: Card): string {
    if (card?.card_back_path) return imageUrl(card.card_back_path);
    return '/card-back.svg';
  }

  // Group user collection by card (set + name + number) and count, like My deck
  function userCollectionGroupKey(card: Card): string {
    const set = (card?.set_id ?? card?.set_name ?? '').trim();
    const name = (card?.name ?? '').trim();
    const num = (card?.number ?? '').trim();
    return `${set}:${name}:${num}`;
  }
  const userCollectionGrouped = $derived.by(() => {
    const list = userCollection || [];
    const map = new Map<string, { card: Card; count: number }>();
    for (const card of list) {
      const key = userCollectionGroupKey(card);
      const existing = map.get(key);
      if (existing) existing.count += 1;
      else map.set(key, { card: { ...card }, count: 1 });
    }
    return Array.from(map.values());
  });

  onMount(async () => {
    try {
      const raw = localStorage.getItem(CATALOGUE_GRID_SETS_KEY);
      if (raw) {
        const arr = JSON.parse(raw) as string[];
        if (Array.isArray(arr)) gridModeForSetId = new Set(arr);
      }
      const userGrid = localStorage.getItem(CATALOGUE_USER_GRID_KEY);
      if (userGrid === 'true' || userGrid === 'false') userCollectionGrid = userGrid === 'true';
    } catch (_) {}
    loadSets();
    try {
      const res = await fetchApi('/api/me', { auth: true });
      if (res.ok) me = await res.json();
      else me = null;
    } catch {
      me = null;
    }
    // Pre-open a user's deck when linked from profile (e.g. /catalogue?user=userId)
    const userId = $page?.url?.searchParams?.get('user') ?? null;
    if (userId) {
      try {
        const profileRes = await fetchApi(`/api/public/users/${encodeURIComponent(userId)}`, { auth: false });
        if (profileRes.ok) {
          const u = await profileRes.json();
          tab = 'users';
          await openUser({
            user_id: u.user_id,
            username: u.username ?? u.poser_username ?? 'User',
            poser_username: u.poser_username ?? null,
            collection_count: u.collection_count ?? 0
          });
          searchUsers(true);
        }
      } catch {
        /* ignore */
      }
    }
  });

  async function loadSets() {
    setsLoading = true;
    try {
      const res = await fetchApi('/api/public/sets');
      if (res.ok) {
        const data = await res.json();
        sets = data.sets || [];
      }
    } finally {
      setsLoading = false;
    }
  }

  async function openSet(set: Set) {
    selectedSet = set;
    selectedCard = null;
    setCardsLoading = true;
    setCards = [];
    try {
      const res = await fetchApi(`/api/public/sets/${set.id}/cards`);
      if (res.ok) {
        const data = await res.json();
        setCards = data.cards || [];
      }
    } finally {
      setCardsLoading = false;
    }
  }

  async function openCard(card: Card) {
    selectedCard = card;
    cardOwnersLoading = true;
    cardOwners = [];
    try {
      const res = await fetchApi(`/api/public/cards/${card.id}/owners`);
      if (res.ok) {
        const data = await res.json();
        cardOwners = data.owners || [];
      }
    } finally {
      cardOwnersLoading = false;
    }
  }

  let searchTimeout: ReturnType<typeof setTimeout> | null = null;
  function onUserQueryInput() {
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => searchUsers(), 300);
  }
  async function searchUsers(keepSelection = false) {
    const q = userQuery.trim();
    usersLoading = true;
    userSearchResults = [];
    if (!keepSelection) selectedUser = null;
    try {
      const res = await fetchApi(`/api/public/users?q=${encodeURIComponent(q)}&limit=30`);
      if (res.ok) {
        const data = await res.json();
        userSearchResults = data.users || [];
      }
    } finally {
      usersLoading = false;
    }
  }

  async function openUser(user: User) {
    selectedUser = user;
    userCollectionLoading = true;
    userCollection = [];
    try {
      const res = await fetchApi(`/api/public/users/${encodeURIComponent(user.user_id)}/collection`);
      if (res.ok) {
        const data = await res.json();
        userCollection = data.cards || [];
        if (data.user && data.user.poser_username !== undefined) selectedUser = { ...selectedUser!, poser_username: data.user.poser_username };
      }
    } finally {
      userCollectionLoading = false;
    }
  }

  function closeSet() {
    selectedSet = null;
    setCards = [];
    selectedCard = null;
  }
  function closeCard() {
    selectedCard = null;
    cardOwners = [];
  }
  function closeUser() {
    selectedUser = null;
    userCollection = [];
  }
</script>

<svelte:head>
  <title>Catalogue · Brutality Cards</title>
</svelte:head>

<main class="app-page catalogue-page min-h-screen py-8 px-4 md:py-10 relative">
  <div class="app-page__bg" aria-hidden="true"></div>
  <div class="texture-overlay" aria-hidden="true"></div>

  <div class="relative z-10 max-w-6xl mx-auto">
    <AppHeader title="Explore" user={me ? { username: me.username ?? '', avatar_url: me.avatar_url, is_admin: me.is_admin, pending_issued_count: me.pending_issued_count } : null} showExploreButton={false} showHomeLink={true} />
    <p class="text-muted-foreground text-sm -mt-4 mb-6">Browse sets and cards, find users, and see who has which cards.</p>

    <div class="flex gap-2 mb-6 border-b border-border pb-2">
      <Button
        variant={tab === 'catalog' ? 'default' : 'ghost'}
        size="sm"
        onclick={() => { tab = 'catalog'; closeUser(); }}
      >
        Catalog
      </Button>
      <Button
        variant={tab === 'users' ? 'default' : 'ghost'}
        size="sm"
        onclick={() => { tab = 'users'; closeSet(); closeCard(); searchUsers(); }}
      >
        Users
      </Button>
    </div>

    {#if tab === 'catalog'}
      <div class="grid gap-8 lg:grid-cols-[280px_1fr]">
        <aside class="space-y-2">
          <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Sets</h2>
          {#if setsLoading}
            <p class="text-sm text-muted-foreground">Loading…</p>
          {:else if sets.length === 0}
            <p class="text-sm text-muted-foreground">No sets yet.</p>
          {:else}
            {#each sets as set}
              <button
                type="button"
                class="cursor-pointer w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors {selectedSet?.id === set.id ? 'bg-primary text-primary-foreground' : 'hover:bg-muted hover:ring-1 hover:ring-border'}"
                onclick={() => openSet(set)}
              >
                {set.name}
              </button>
            {/each}
          {/if}
        </aside>

        <div class="min-w-0 overflow-visible">
          {#if selectedSet}
            {@const isSetGrid = gridModeForSetId.has(selectedSet.id)}
            <div class="catalogue-set__header flex items-center justify-between gap-2 mb-4">
              <div class="flex items-center gap-2">
                <Button variant="ghost" size="sm" onclick={closeSet}>← Back</Button>
                <h2 class="text-lg font-semibold">{selectedSet.name}</h2>
              </div>
              <button
                type="button"
                class="catalogue-set__toggle rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                aria-label={isSetGrid ? 'Show as scrolling row' : 'Show as grid'}
                title={isSetGrid ? 'Row view' : 'Grid view'}
                onclick={() => toggleSetViewMode(selectedSet.id)}
              >
                {#if isSetGrid}
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                {:else}
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                {/if}
              </button>
            </div>
            {#if setCardsLoading}
              <p class="text-muted-foreground text-sm">Loading cards…</p>
            {:else if setCards.length === 0}
              <p class="text-muted-foreground text-sm">No cards in this set.</p>
            {:else}
              <div class="catalogue-set catalogue-set--grid transition-[opacity,transform] duration-300 ease-out" class:catalogue-set--grid={isSetGrid}>
                {#if isSetGrid}
                  <div class="catalogue-set__grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                    {#each setCards as card}
                      <div class="catalogue-set__grid-card flex flex-col items-center">
                        <button
                          type="button"
                          class="cursor-pointer w-full focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg overflow-visible transition-transform hover:scale-[1.02] active:scale-[0.99] {selectedCard?.id === card.id ? 'ring-2 ring-primary' : ''}"
                          onclick={() => openCard(card)}
                        >
                          <TradingCard
                            id={card.id}
                            name={card.name}
                            number={card.number}
                            set={card.set_name}
                            types={card.types}
                            subtypes={card.subtypes}
                            supertype={card.supertype}
                            rarity={card.rarity}
                            img={card.image_path ? imageUrl(card.image_path) : ''}
                            back={selectedSet ? setBackUrl(selectedSet) : '/card-back.svg'}
                            noTilt
                            noPop
                          />
                        </button>
                        <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{card.name}</span>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <div class="catalogue-row__scroll flex gap-6 overflow-x-auto overflow-y-visible pb-2 -mx-1 px-1">
                    {#each setCards as card}
                      <div class="catalogue-row__card flex flex-col items-center flex-shrink-0 w-[min(240px,68vw)] max-w-[240px]">
                        <button
                          type="button"
                          class="cursor-pointer w-full focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg overflow-visible transition-transform hover:scale-[1.02] active:scale-[0.99] {selectedCard?.id === card.id ? 'ring-2 ring-primary' : ''}"
                          onclick={() => openCard(card)}
                        >
                          <TradingCard
                            id={card.id}
                            name={card.name}
                            number={card.number}
                            set={card.set_name}
                            types={card.types}
                            subtypes={card.subtypes}
                            supertype={card.supertype}
                            rarity={card.rarity}
                            img={card.image_path ? imageUrl(card.image_path) : ''}
                            back={selectedSet ? setBackUrl(selectedSet) : '/card-back.svg'}
                            noTilt
                            noPop
                          />
                        </button>
                        <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{card.name}</span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>

              {#if selectedCard}
                <section
                  class="search-card-detail mt-8 rounded-xl border border-border bg-card p-5 relative z-10"
                  aria-label="Card details"
                >
                  <div class="flex flex-wrap items-start justify-between gap-4">
                    <div class="min-w-0">
                      <h3 class="font-semibold text-lg">{selectedCard.name}</h3>
                      <p class="text-sm text-muted-foreground">{selectedCard.set_name} · {selectedCard.rarity}</p>
                      {#if cardOwnersLoading}
                        <p class="text-sm text-muted-foreground mt-3">Loading owners…</p>
                      {:else if cardOwners.length === 0}
                        <p class="text-sm text-muted-foreground mt-3">No one has synced this card yet. Sync your collection from My deck to appear here.</p>
                      {:else}
                        <p class="text-sm font-medium mt-3">Owned by</p>
                        <ul class="flex flex-wrap gap-2 mt-1">
                          {#each cardOwners as owner}
                            <li>
                              <button
                                type="button"
                                class="cursor-pointer text-sm text-primary hover:underline hover:text-primary/90 transition-colors"
                                onclick={() => { tab = 'users'; closeCard(); openUser({ user_id: owner.user_id ?? '', username: owner.username, collection_count: 0 }); }}
                              >
                                @{owner.username}
                              </button>
                            </li>
                          {/each}
                        </ul>
                      {/if}
                    </div>
                    <Button variant="ghost" size="sm" onclick={closeCard}>Close</Button>
                  </div>
                </section>
              {/if}
            {/if}
          {:else}
            <p class="text-muted-foreground text-sm">Select a set to view its cards.</p>
          {/if}
        </div>
      </div>
    {:else}
      <div class="grid gap-8 lg:grid-cols-[280px_1fr]">
        <aside class="space-y-3">
          <h2 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Users</h2>
          <label for="user-search" class="sr-only">Filter users by username</label>
          <input
            id="user-search"
            type="search"
            class="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
            placeholder="Filter by username…"
            bind:value={userQuery}
            oninput={onUserQueryInput}
          />
          {#if usersLoading}
            <p class="text-sm text-muted-foreground">Searching…</p>
          {:else if userSearchResults.length === 0 && userQuery.trim() !== ''}
            <p class="text-sm text-muted-foreground">No users found.</p>
          {:else if userSearchResults.length === 0}
            <p class="text-sm text-muted-foreground">Type to search users.</p>
          {:else}
            <ul class="space-y-1 max-h-[60vh] overflow-y-auto pr-1">
              {#each userSearchResults as u}
                <li>
                  <button
                    type="button"
                    class="cursor-pointer w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors {selectedUser?.user_id === u.user_id ? 'bg-primary text-primary-foreground' : 'hover:bg-muted hover:ring-1 hover:ring-border'}"
                    onclick={() => openUser(u)}
                  >
                    <span class="font-medium">@{u.username}</span>
                    <span class="block text-xs opacity-80 mt-0.5">{u.collection_count} cards</span>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </aside>

        <div class="min-w-0 overflow-visible">
        {#if selectedUser}
          <div>
            <div class="catalogue-set__header flex items-center justify-between gap-2 mb-4">
              <div class="flex items-center gap-2">
                <Button variant="ghost" size="sm" onclick={closeUser}>← Back</Button>
                <h2 class="text-lg font-semibold">@{selectedUser.username}</h2>
                <span class="text-sm text-muted-foreground">({selectedUser.collection_count} cards)</span>
                <a
                  href="/u/{encodeURIComponent(selectedUser.user_id)}"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-xs text-muted-foreground hover:text-foreground underline"
                >
                  Profile
                </a>
              </div>
              <button
                type="button"
                class="catalogue-set__toggle rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                aria-label={userCollectionGrid ? 'Show as scrolling row' : 'Show as grid'}
                title={userCollectionGrid ? 'Row view' : 'Grid view'}
                onclick={toggleUserCollectionView}
              >
                {#if userCollectionGrid}
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                {:else}
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                {/if}
              </button>
            </div>
            {#if userCollectionLoading}
              <p class="text-muted-foreground text-sm">Loading collection…</p>
            {:else if userCollection.length === 0}
              <p class="text-muted-foreground text-sm">No cards in collection yet. They can sync from My deck.</p>
            {:else}
              <div class="catalogue-set catalogue-set--grid transition-[opacity,transform] duration-300 ease-out" class:catalogue-set--grid={userCollectionGrid}>
                {#if userCollectionGrid}
                  <div class="catalogue-set__grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                    {#each userCollectionGrouped as { card, count } (userCollectionGroupKey(card))}
                      <div class="catalogue-set__grid-card flex flex-col items-center relative">
                        <div class="w-full relative">
                          <TradingCard
                            id={card.id}
                            name={card.name}
                            number={card.number}
                            set={card.set_name}
                            types={card.types}
                            subtypes={card.subtypes}
                            supertype={card.supertype}
                            rarity={card.rarity}
                            img={card.image_path ? imageUrl(card.image_path) : ''}
                            back={cardBackUrl(card)}
                            noTilt
                            noPop
                          />
                          {#if count > 1}
                            <span class="absolute top-1 left-1/2 -translate-x-1/2 z-10 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-semibold text-white tabular-nums" aria-label="{count} copies">×{count}</span>
                          {/if}
                        </div>
                        <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{count} {count === 1 ? 'copy' : 'copies'}</span>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <div class="catalogue-row__scroll flex gap-6 overflow-x-auto overflow-y-visible pb-2 -mx-1 px-1">
                    {#each userCollectionGrouped as { card, count } (userCollectionGroupKey(card))}
                      <div class="catalogue-row__card flex flex-col items-center flex-shrink-0 w-[min(240px,68vw)] max-w-[240px] relative">
                        <div class="w-full relative">
                          <TradingCard
                            id={card.id}
                            name={card.name}
                            number={card.number}
                            set={card.set_name}
                            types={card.types}
                            subtypes={card.subtypes}
                            supertype={card.supertype}
                            rarity={card.rarity}
                            img={card.image_path ? imageUrl(card.image_path) : ''}
                            back={cardBackUrl(card)}
                            noTilt
                            noPop
                          />
                          {#if count > 1}
                            <span class="absolute top-1 left-1/2 -translate-x-1/2 z-10 rounded-md bg-black/75 px-1.5 py-0.5 text-xs font-semibold text-white tabular-nums" aria-label="{count} copies">×{count}</span>
                          {/if}
                        </div>
                        <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{count} {count === 1 ? 'copy' : 'copies'}</span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {:else}
          <p class="text-muted-foreground text-sm">Select a user from the list to view their collection.</p>
        {/if}
        </div>
      </div>
    {/if}
  </div>
</main>

<style>
  .catalogue-row__scroll {
    scroll-snap-type: x proximity;
    -webkit-overflow-scrolling: touch;
    scroll-behavior: smooth;
  }
  .catalogue-row__scroll::-webkit-scrollbar {
    height: 6px;
  }
  .catalogue-row__scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .catalogue-row__scroll::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 3px;
  }
  .catalogue-row__scroll::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.3);
  }
  .catalogue-row__card {
    scroll-snap-align: start;
  }

  .catalogue-set__grid-card {
    max-width: 140px;
    margin-left: auto;
    margin-right: auto;
  }
  @media (min-width: 640px) {
    .catalogue-set__grid-card { max-width: 150px; }
  }
  @media (min-width: 768px) {
    .catalogue-set__grid-card { max-width: 160px; }
  }
  @media (min-width: 1024px) {
    .catalogue-set__grid-card { max-width: 150px; }
  }
</style>
