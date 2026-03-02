<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import TradingCard from '$lib/components/Card.svelte';

  const API = import.meta.env.VITE_API_URL ?? '';

  type CardSet = { id: string; name: string; slug: string; description: string; created_at: string; updated_at: string };
  type CardItem = {
    id: string; set_id: string; name: string; number: string; rarity: string;
    set_name: string; quote: string; artwork: string; image_path: string;
    types: string[]; subtypes: string; supertype: string; created_at: string; updated_at: string;
  };

  let user: { username: string; is_admin: boolean } | null = $state(null);
  let sets: CardSet[] = $state([]);
  let selectedSet: CardSet | null = $state(null);
  let cards: CardItem[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let success = $state('');

  // View: 'sets' | 'cards' — dynamic, no stacked columns
  let view: 'sets' | 'cards' = $state('sets');

  // Modals
  let showCreateSet = $state(false);
  let showAddCard = $state(false);
  let previewCard: CardItem | null = $state(null);

  // Create set form
  let newSetName = $state('');
  let newSetDescription = $state('');
  let creatingSet = $state(false);

  // Add card form (simplified: name, rarity, set name disabled, image)
  let cardName = $state('');
  let cardRarity = $state('common');
  let cardImageFile: File | null = $state(null);
  let addingCard = $state(false);
  let imagePreviewUrl = $state('');

  // Camera
  let showCamera = $state(false);
  let cameraError = $state('');
  let videoEl: HTMLVideoElement | null = $state(null);
  let mediaStream: MediaStream | null = $state(null);

  function setCardImageFile(file: File | null) {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    imagePreviewUrl = '';
    cardImageFile = file;
    if (file) imagePreviewUrl = URL.createObjectURL(file);
  }

  function openTakePicture() {
    setCardImageFile(null);
    const input = document.getElementById('card-image') as HTMLInputElement;
    if (input) input.value = '';
    cameraError = '';
    showCamera = true;
  }

  function stopCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (videoEl) videoEl.srcObject = null;
    // Do not set videoEl = null here — the $effect cleanup runs when videoEl is first set and would clear the ref before startCamera() runs.
  }

  function startCamera() {
    if (mediaStream || !videoEl) return;
    cameraError = '';
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
        mediaStream = stream;
        if (videoEl) {
          videoEl.srcObject = stream;
          const p = videoEl.play();
          if (p !== undefined) p.catch(() => {});
        }
      })
      .catch((e) => {
        cameraError = e.message || 'Camera access denied';
        showCamera = false;
      });
  }

  function capturePhoto() {
    if (!videoEl || !mediaStream) return;
    const w = videoEl.videoWidth;
    const h = videoEl.videoHeight;
    if (!w || !h) return;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoEl, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setCardImageFile(new File([blob], 'capture.png', { type: 'image/png' }));
        stopCamera();
        showCamera = false;
      },
      'image/png'
    );
  }

  $effect(() => {
    if (showCamera && showAddCard && videoEl) {
      startCamera();
      return () => stopCamera();
    }
  });

  onMount(async () => {
    try {
      const meRes = await fetch(`${API}/api/me`, { credentials: 'include' });
      if (meRes.status === 401) {
        goto('/');
        return;
      }
      if (!meRes.ok) throw new Error('Failed to load user');
      const me = await meRes.json();
      user = me;
      if (!me.is_admin) {
        goto('/wallet');
        return;
      }
      const setsRes = await fetch(`${API}/api/admin/sets`, { credentials: 'include' });
      if (!setsRes.ok) throw new Error('Failed to load sets');
      const data = await setsRes.json();
      sets = data.sets || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  async function loadCards(setId: string) {
    const res = await fetch(`${API}/api/admin/sets/${setId}/cards`, { credentials: 'include' });
    if (!res.ok) throw new Error('Failed to load cards');
    const data = await res.json();
    cards = data.cards || [];
  }

  function openSet(s: CardSet) {
    selectedSet = s;
    loadCards(s.id);
    view = 'cards';
  }

  function backToSets() {
    view = 'sets';
    selectedSet = null;
    cards = [];
  }

  function openCreateSet() {
    showCreateSet = true;
    newSetName = '';
    newSetDescription = '';
  }

  async function createSet() {
    if (!newSetName.trim()) return;
    creatingSet = true;
    error = '';
    success = '';
    try {
      const form = new FormData();
      form.append('name', newSetName.trim());
      form.append('slug', '');
      form.append('description', newSetDescription.trim());
      const res = await fetch(`${API}/api/admin/sets`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create set');
      }
      const created = await res.json();
      sets = [...sets, created];
      showCreateSet = false;
      success = 'Set created.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create set';
    } finally {
      creatingSet = false;
    }
  }

  function openAddCard() {
    if (!selectedSet) return;
    cardName = '';
    cardRarity = 'common';
    setCardImageFile(null);
    showCamera = false;
    showAddCard = true;
  }

  async function addCard() {
    if (!selectedSet || !cardName.trim()) return;
    addingCard = true;
    error = '';
    success = '';
    try {
      const form = new FormData();
      form.append('name', cardName.trim());
      form.append('number', '');
      form.append('rarity', cardRarity);
      form.append('set_name', selectedSet.name);
      form.append('quote', '');
      form.append('artwork', '');
      form.append('types', 'TradingCard');
      form.append('subtypes', 'trading-cards');
      form.append('supertype', 'trading-card');
      if (cardImageFile) form.append('image', cardImageFile);
      const res = await fetch(`${API}/api/admin/sets/${selectedSet.id}/cards`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to add card');
      }
      const created = await res.json();
      cards = [...cards, created];
      showAddCard = false;
      success = 'Card added.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to add card';
    } finally {
      addingCard = false;
    }
  }

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = API.replace(/\/$/, '');
    return path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }

  function closeCreateSet() {
    showCreateSet = false;
  }

  function closeAddCard() {
    showAddCard = false;
    showCamera = false;
    stopCamera();
    videoEl = null;
  }
</script>

<main class="manage-cards-page py-4 px-3 sm:py-6 sm:px-4">
  <!-- Header -->
  <header class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
    <div class="flex items-center gap-2">
      {#if view === 'cards' && selectedSet}
        <Button variant="ghost" size="icon-sm" onclick={backToSets} aria-label="Back to sets">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        </Button>
        <div>
          <h1 class="text-xl font-semibold">{selectedSet.name}</h1>
          <p class="text-muted-foreground text-sm">{cards.length} cards</p>
        </div>
      {:else}
        <div>
          <h1 class="text-xl font-semibold">Manage Cards</h1>
          <p class="text-muted-foreground text-sm">Sets and collections</p>
        </div>
      {/if}
    </div>
    <div class="flex gap-2">
      {#if view === 'sets'}
        <Button size="sm" onclick={openCreateSet}>New set</Button>
      {:else if selectedSet}
        <Button size="sm" onclick={openAddCard}>Add card</Button>
      {/if}
      <Button variant="outline" size="sm" href="/admin">Admin</Button>
      <Button variant="outline" size="sm" href="/wallet">Wallet</Button>
    </div>
  </header>

  {#if error}
    <div class="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
  {/if}
  {#if success}
    <div class="mb-4 p-3 rounded-lg bg-green-500/10 text-green-700 dark:text-green-400 text-sm">{success}</div>
  {/if}

  {#if loading}
    <div class="py-12 text-center text-muted-foreground">Loading…</div>
  {:else if view === 'sets'}
    <!-- Sets list -->
    <ul class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each sets as s}
        <li>
          <button
            type="button"
            class="w-full text-left p-4 rounded-xl border border-border bg-card hover:bg-muted/50 transition-colors"
            onclick={() => openSet(s)}
          >
            <span class="font-medium">{s.name}</span>
            <span class="text-muted-foreground text-sm block mt-0.5">{s.slug}</span>
          </button>
        </li>
      {/each}
    </ul>
    {#if sets.length === 0}
      <div class="py-12 text-center text-muted-foreground rounded-xl border border-dashed border-border">
        <p class="mb-4">No sets yet.</p>
        <Button onclick={openCreateSet}>Create your first set</Button>
      </div>
    {/if}
  {:else if view === 'cards' && selectedSet}
    <!-- Cards list with Preview -->
    {#if cards.length === 0}
      <div class="py-12 text-center text-muted-foreground rounded-xl border border-dashed border-border">
        <p class="mb-4">No cards in this set.</p>
        <Button onclick={openAddCard}>Add a card</Button>
      </div>
    {:else}
      <ul class="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {#each cards as c}
          <li class="flex flex-col rounded-xl border border-border bg-card overflow-hidden">
            <div class="aspect-[0.718] w-full bg-muted/30 flex items-center justify-center shrink-0">
              {#if c.image_path}
                <img src={imageUrl(c.image_path)} alt={c.name} class="w-full h-full object-contain" />
              {:else}
                <span class="text-muted-foreground text-sm">No image</span>
              {/if}
            </div>
            <div class="p-3 flex flex-col gap-2 flex-1">
              <span class="font-medium truncate">{c.name}</span>
              <span class="text-muted-foreground text-xs capitalize">{c.rarity}</span>
              <Button variant="outline" size="sm" class="w-full mt-auto" onclick={() => (previewCard = c)}>
                Preview
              </Button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}

  <!-- Modal: Create set -->
  {#if showCreateSet}
    <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="create-set-title">
      <div class="absolute inset-0 bg-black/60" onclick={closeCreateSet}></div>
      <div class="relative w-full max-w-md bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-xl p-6 max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
        <h2 id="create-set-title" class="text-lg font-semibold mb-1">Create set</h2>
        <p class="text-muted-foreground text-sm mb-4">Slug is derived from the name.</p>
        <div class="space-y-4">
          <div>
            <label for="set-name" class="block text-sm font-medium mb-1">Name</label>
            <input id="set-name" type="text" bind:value={newSetName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. Genesis" />
          </div>
          <div>
            <label for="set-desc" class="block text-sm font-medium mb-1">Description (optional)</label>
            <textarea id="set-desc" bind:value={newSetDescription} rows="2" class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Optional"></textarea>
          </div>
          <div class="flex gap-2 pt-2">
            <Button onclick={createSet} disabled={creatingSet || !newSetName.trim()}>
              {creatingSet ? 'Creating…' : 'Create'}
            </Button>
            <Button variant="outline" onclick={closeCreateSet}>Cancel</Button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Modal: Add card (simplified) -->
  {#if showAddCard && selectedSet}
    <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="add-card-title">
      <div class="absolute inset-0 bg-black/60" onclick={closeAddCard}></div>
      <div class="relative w-full max-w-md bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-xl p-6 max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()}>
        <h2 id="add-card-title" class="text-lg font-semibold mb-4">Add card</h2>
        <div class="space-y-4">
          <div>
            <label for="card-name" class="block text-sm font-medium mb-1">Name *</label>
            <input id="card-name" type="text" bind:value={cardName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Card name" />
          </div>
          <div>
            <label for="card-rarity" class="block text-sm font-medium mb-1">Rarity</label>
            <select id="card-rarity" bind:value={cardRarity} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
              <option value="common">common</option>
              <option value="uncommon">uncommon</option>
              <option value="rare">rare</option>
              <option value="legendary">legendary</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Set</label>
            <input type="text" value={selectedSet.name} disabled class="w-full rounded-md border border-input bg-muted/50 px-3 py-2 text-sm text-muted-foreground cursor-not-allowed" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">Image (PNG)</label>
            <div class="flex flex-wrap gap-2 items-center">
              <input
                id="card-image"
                type="file"
                accept=".png,image/png"
                class="text-sm file:mr-2 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground"
                onchange={(e) => { setCardImageFile((e.target as HTMLInputElement).files?.[0] ?? null); showCamera = false; }}
              />
              <span class="text-muted-foreground text-xs">or</span>
              <Button type="button" variant="outline" size="sm" onclick={openTakePicture}>Take picture</Button>
            </div>
            {#if showCamera}
              <div class="mt-3 p-3 rounded-lg border border-border bg-muted/30 space-y-2">
                {#if cameraError}
                  <p class="text-sm text-destructive">{cameraError}</p>
                {:else}
                  <div class="rounded-lg overflow-hidden bg-black max-w-full min-h-[180px]">
                    <video bind:this={videoEl} autoplay playsinline muted class="block w-full min-h-[180px] max-h-40 object-cover"></video>
                  </div>
                  <div class="flex gap-2">
                    <Button type="button" size="sm" onclick={capturePhoto}>Capture</Button>
                    <Button type="button" variant="outline" size="sm" onclick={() => { stopCamera(); showCamera = false; }}>Cancel</Button>
                  </div>
                {/if}
              </div>
            {/if}
            {#if cardImageFile && !showCamera}
              <div class="mt-2 flex items-center gap-2">
                <img src={imagePreviewUrl} alt="Preview" class="h-14 w-14 object-contain rounded border border-border" />
                <span class="text-sm text-muted-foreground truncate flex-1">{cardImageFile.name}</span>
                <Button type="button" variant="ghost" size="sm" onclick={() => { setCardImageFile(null); (document.getElementById('card-image') as HTMLInputElement).value = ''; }}>Clear</Button>
              </div>
            {/if}
          </div>
          <div class="flex gap-2 pt-2">
            <Button onclick={addCard} disabled={addingCard || !cardName.trim()}>
              {addingCard ? 'Adding…' : 'Add card'}
            </Button>
            <Button variant="outline" onclick={closeAddCard}>Cancel</Button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Modal: Preview (holographic card) -->
  {#if previewCard}
    <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70" role="dialog" aria-modal="true" aria-label="Card preview" onclick={() => (previewCard = null)}>
      <div class="max-w-[min(280px,95vw)]" onclick={(e) => e.stopPropagation()}>
        <TradingCard
          id={previewCard.id}
          name={previewCard.name}
          number={previewCard.number}
          set={previewCard.set_name}
          types={previewCard.types?.length ? previewCard.types : ['TradingCard']}
          subtypes={previewCard.subtypes || 'trading-cards'}
          supertype={previewCard.supertype || 'trading-card'}
          rarity={previewCard.rarity}
          img={previewCard.image_path ? imageUrl(previewCard.image_path) : ''}
        />
      </div>
      <button
        type="button"
        class="absolute top-4 right-4 p-2 rounded-full bg-black/50 text-white hover:bg-black/70"
        aria-label="Close preview"
        onclick={() => (previewCard = null)}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    </div>
  {/if}
</main>

<style>
  .manage-cards-page {
    max-width: 1200px;
    margin: 0 auto;
  }
</style>
