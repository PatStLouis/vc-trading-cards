<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import TradingCard from '$lib/components/Card.svelte';
  import AppIcon from '$lib/components/AppIcon.svelte';

  const API = import.meta.env.VITE_API_URL ?? '';

  type Set = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string };
  type Card = {
    id: string; set_id: string; name: string; number: string; rarity: string; set_name: string;
    image_path: string; types: string[]; subtypes: string; supertype: string; card_back_path?: string;
  };
  type User = { discord_sub: string; username: string; collection_count: number };

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
  let cardOwners: { discord_sub: string; username: string }[] = $state([]);
  let cardOwnersLoading = $state(false);

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

  onMount(() => {
    loadSets();
  });

  async function loadSets() {
    setsLoading = true;
    try {
      const res = await fetch(`${API}/api/public/sets`);
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
      const res = await fetch(`${API}/api/public/sets/${set.id}/cards`);
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
      const res = await fetch(`${API}/api/public/cards/${card.id}/owners`);
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
  async function searchUsers() {
    const q = userQuery.trim();
    usersLoading = true;
    userSearchResults = [];
    selectedUser = null;
    try {
      const res = await fetch(`${API}/api/public/users?q=${encodeURIComponent(q)}&limit=30`);
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
      const res = await fetch(`${API}/api/public/users/${encodeURIComponent(user.discord_sub)}/collection`);
      if (res.ok) {
        const data = await res.json();
        userCollection = data.cards || [];
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
  <title>Search · Tritone Cards</title>
</svelte:head>

<main class="search-page min-h-screen py-8 px-4 md:py-10">
  <div class="max-w-6xl mx-auto">
    <nav class="mb-6 flex items-center gap-4 text-sm">
      <a href="/" class="cursor-pointer flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors rounded px-1 -mx-1 hover:bg-muted/50">
        <AppIcon size="sm" />
        <span>Tritone Cards</span>
      </a>
      <a href="/search" class="cursor-pointer text-foreground font-medium rounded px-1 -mx-1 hover:bg-muted/50 transition-colors">Explore</a>
    </nav>
    <header class="mb-8">
      <h1 class="font-display text-3xl md:text-4xl tracking-tight uppercase">Explore</h1>
      <p class="text-muted-foreground mt-1">Browse sets and cards, find users, and see who has which cards.</p>
    </header>

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
        onclick={() => { tab = 'users'; closeSet(); closeCard(); }}
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
            <div class="mb-4 flex items-center gap-2">
              <Button variant="ghost" size="sm" onclick={closeSet}>← Back</Button>
              <h2 class="text-lg font-semibold">{selectedSet.name}</h2>
            </div>
            {#if setCardsLoading}
              <p class="text-muted-foreground text-sm">Loading cards…</p>
            {:else if setCards.length === 0}
              <p class="text-muted-foreground text-sm">No cards in this set.</p>
            {:else}
              <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {#each setCards as card}
                  <div class="flex flex-col items-center">
                    <button
                      type="button"
                      class="cursor-pointer w-full max-w-[200px] focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg overflow-visible transition-transform hover:scale-[1.02] active:scale-[0.99] {selectedCard?.id === card.id ? 'ring-2 ring-primary' : ''}"
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
                      />
                    </button>
                    <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{card.name}</span>
                  </div>
                {/each}
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
                                onclick={() => { tab = 'users'; closeCard(); openUser({ discord_sub: owner.discord_sub, username: owner.username, collection_count: 0 }); }}
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
      <div class="space-y-6">
        <div>
          <label for="user-search" class="sr-only">Search users</label>
          <input
            id="user-search"
            type="search"
            class="w-full max-w-md rounded-lg border border-input bg-background px-4 py-2 text-sm"
            placeholder="Search by username…"
            bind:value={userQuery}
            oninput={onUserQueryInput}
          />
        </div>
        {#if usersLoading}
          <p class="text-muted-foreground text-sm">Searching…</p>
        {:else if selectedUser}
          <div>
            <div class="mb-4 flex items-center gap-2">
              <Button variant="ghost" size="sm" onclick={closeUser}>← Back</Button>
              <h2 class="text-lg font-semibold">@{selectedUser.username}</h2>
              <span class="text-sm text-muted-foreground">({selectedUser.collection_count} cards)</span>
            </div>
            {#if userCollectionLoading}
              <p class="text-muted-foreground text-sm">Loading collection…</p>
            {:else if userCollection.length === 0}
              <p class="text-muted-foreground text-sm">No cards in collection yet. They can sync from My deck.</p>
            {:else}
              <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {#each userCollection as card}
                  <div class="flex flex-col items-center">
                    <div class="w-full max-w-[200px]">
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
                      />
                    </div>
                    <span class="mt-2 text-xs text-muted-foreground truncate w-full text-center">{card.name}</span>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          {#if userSearchResults.length === 0 && userQuery.trim() !== ''}
            <p class="text-muted-foreground text-sm">No users found.</p>
          {:else if userSearchResults.length > 0}
            <ul class="space-y-2">
              {#each userSearchResults as u}
                <li>
                  <button
                    type="button"
                    class="cursor-pointer w-full text-left px-4 py-3 rounded-lg border border-border bg-card hover:bg-muted/50 hover:border-primary/30 hover:shadow-sm transition-all flex items-center justify-between"
                    onclick={() => openUser(u)}
                  >
                    <span class="font-medium">@{u.username}</span>
                    <span class="text-sm text-muted-foreground">{u.collection_count} cards</span>
                  </button>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-muted-foreground text-sm">Type a username to search. Users who have synced their collection will appear here.</p>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
</main>
