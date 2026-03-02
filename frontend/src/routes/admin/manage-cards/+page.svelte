<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import * as Table from '$lib/components/ui/table';

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

  // Create set form
  let showCreateSet = $state(false);
  let newSetName = $state('');
  let newSetSlug = $state('');
  let newSetDescription = $state('');
  let creatingSet = $state(false);

  // Add card form
  let showAddCard = $state(false);
  let cardName = $state('');
  let cardNumber = $state('');
  let cardRarity = $state('common');
  let cardSetName = $state('');
  let cardQuote = $state('');
  let cardArtwork = $state('');
  let cardTypes = $state('TradingCard');
  let cardSubtypes = $state('trading-cards');
  let cardSupertype = $state('trading-card');
  let cardImageFile: File | null = $state(null);
  let addingCard = $state(false);
  let imagePreviewUrl = $state('');

  // Camera capture
  let showCamera = $state(false);
  let cameraError = $state('');
  let videoEl: HTMLVideoElement | null = $state(null);
  let mediaStream: MediaStream | null = $state(null);

  function startCamera() {
    if (mediaStream || !videoEl) return;
    cameraError = '';
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
        mediaStream = stream;
        if (videoEl) {
          videoEl.srcObject = stream;
          videoEl.play();
        }
      })
      .catch((e) => {
        cameraError = e.message || 'Camera access denied';
        showCamera = false;
      });
  }

  function stopCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (videoEl) videoEl.srcObject = null;
    videoEl = null;
  }

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

  function selectSet(s: CardSet) {
    selectedSet = s;
    cards = [];
    if (s) loadCards(s.id);
  }

  async function createSet() {
    if (!newSetName.trim()) return;
    creatingSet = true;
    error = '';
    success = '';
    try {
      const form = new FormData();
      form.append('name', newSetName.trim());
      form.append('slug', newSetSlug.trim());
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
      newSetName = '';
      newSetSlug = '';
      newSetDescription = '';
      showCreateSet = false;
      success = 'Set created.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create set';
    } finally {
      creatingSet = false;
    }
  }

  function setAddCardDefaults() {
    if (selectedSet) {
      cardSetName = selectedSet.name;
    }
  }

  async function addCard() {
    if (!selectedSet || !cardName.trim()) return;
    addingCard = true;
    error = '';
    success = '';
    try {
      const form = new FormData();
      form.append('name', cardName.trim());
      form.append('number', cardNumber.trim());
      form.append('rarity', cardRarity);
      form.append('set_name', cardSetName.trim());
      form.append('quote', cardQuote.trim());
      form.append('artwork', cardArtwork.trim());
      form.append('types', cardTypes.trim());
      form.append('subtypes', cardSubtypes.trim());
      form.append('supertype', cardSupertype.trim());
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
      cardName = '';
      cardNumber = '';
      cardQuote = '';
      cardArtwork = '';
      setCardImageFile(null);
      showCamera = false;
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
</script>

<main class="admin-page py-6 px-4">
  <Card.Root class="border border-border bg-card text-card-foreground rounded-xl mb-6">
    <Card.Header class="flex flex-row flex-wrap items-center justify-between gap-4 pb-4 border-b border-border">
      <div>
        <Card.Title class="text-xl font-semibold">Manage Cards</Card.Title>
        <Card.Description class="text-muted-foreground text-sm mt-1">
          Card collections and sets
          {#if user}
            · Logged in as @{user.username}
          {/if}
        </Card.Description>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" href="/admin">Admin</Button>
        <Button variant="outline" size="sm" href="/wallet">Wallet</Button>
      </div>
    </Card.Header>
  </Card.Root>

  {#if loading}
    <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-8">
      <Card.Content>
        <p class="text-muted-foreground">Loading…</p>
      </Card.Content>
    </Card.Root>
  {:else}
    {#if error}
      <div class="mb-4 p-4 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>
    {/if}
    {#if success}
      <div class="mb-4 p-4 rounded-lg bg-green-500/10 text-green-700 dark:text-green-400 text-sm">{success}</div>
    {/if}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Sets list -->
      <Card.Root class="border border-border bg-card text-card-foreground rounded-xl overflow-hidden">
        <Card.Header class="flex flex-row items-center justify-between pb-4 border-b border-border">
          <Card.Title class="text-lg font-medium">Sets</Card.Title>
          <Button variant="outline" size="sm" onclick={() => { showCreateSet = true; showAddCard = false; }}>New set</Button>
        </Card.Header>
        <Card.Content class="p-0">
          <ul class="divide-y divide-border">
            {#each sets as s}
              <li>
                <button
                  type="button"
                  class="w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors {selectedSet?.id === s.id ? 'bg-muted' : ''}"
                  onclick={() => selectSet(s)}
                >
                  <span class="font-medium">{s.name}</span>
                  <span class="text-muted-foreground text-sm block">{s.slug}</span>
                </button>
              </li>
            {/each}
          </ul>
          {#if sets.length === 0}
            <p class="p-6 text-center text-muted-foreground text-sm">No sets yet. Create one to get started.</p>
          {/if}
        </Card.Content>
      </Card.Root>

      <!-- Create set form -->
      {#if showCreateSet}
        <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-6">
          <Card.Header class="pb-4">
            <Card.Title class="text-lg font-medium">Create set</Card.Title>
            <Card.Description class="text-muted-foreground text-sm">Name, slug (URL-friendly), and description.</Card.Description>
          </Card.Header>
          <Card.Content class="space-y-4">
            <div>
              <label for="set-name" class="block text-sm font-medium mb-1">Name</label>
              <input id="set-name" type="text" bind:value={newSetName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. Genesis" />
            </div>
            <div>
              <label for="set-slug" class="block text-sm font-medium mb-1">Slug</label>
              <input id="set-slug" type="text" bind:value={newSetSlug} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. genesis (optional)" />
            </div>
            <div>
              <label for="set-desc" class="block text-sm font-medium mb-1">Description</label>
              <textarea id="set-desc" bind:value={newSetDescription} rows="2" class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Optional"></textarea>
            </div>
            <div class="flex gap-2">
              <Button onclick={createSet} disabled={creatingSet || !newSetName.trim()}>
                {creatingSet ? 'Creating…' : 'Create set'}
              </Button>
              <Button variant="outline" onclick={() => { showCreateSet = false; }}>Cancel</Button>
            </div>
          </Card.Content>
        </Card.Root>
      {/if}

      <!-- Cards in selected set + Add card -->
      <div class="lg:col-span-2 space-y-6">
        {#if selectedSet}
          <Card.Root class="border border-border bg-card text-card-foreground rounded-xl overflow-hidden">
            <Card.Header class="flex flex-row items-center justify-between pb-4 border-b border-border">
              <Card.Title class="text-lg font-medium">Cards in “{selectedSet.name}”</Card.Title>
              <Button
                variant="outline"
                size="sm"
                onclick={() => { showAddCard = true; showCreateSet = false; setAddCardDefaults(); }}
              >
                Add card
              </Button>
            </Card.Header>
            <Card.Content class="p-0">
              <Table.Root>
                <Table.Header>
                  <Table.Row>
                    <Table.Head>#</Table.Head>
                    <Table.Head>Name</Table.Head>
                    <Table.Head>Rarity</Table.Head>
                    <Table.Head>Image</Table.Head>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {#each cards as c}
                    <Table.Row>
                      <Table.Cell class="font-mono text-sm">{c.number || '—'}</Table.Cell>
                      <Table.Cell class="font-medium">{c.name}</Table.Cell>
                      <Table.Cell class="text-sm">{c.rarity}</Table.Cell>
                      <Table.Cell>
                        {#if c.image_path}
                          <img src={imageUrl(c.image_path)} alt={c.name} class="h-10 w-10 object-contain rounded border border-border" />
                        {:else}
                          <span class="text-muted-foreground text-sm">—</span>
                        {/if}
                      </Table.Cell>
                    </Table.Row>
                  {/each}
                </Table.Body>
              </Table.Root>
              {#if cards.length === 0}
                <p class="p-6 text-center text-muted-foreground text-sm">No cards in this set. Add one below.</p>
              {/if}
            </Card.Content>
          </Card.Root>

          <!-- Add card form -->
          {#if showAddCard}
            <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-6">
              <Card.Header class="pb-4">
                <Card.Title class="text-lg font-medium">Add card</Card.Title>
                <Card.Description class="text-muted-foreground text-sm">Upload a PNG and fill in fields.</Card.Description>
              </Card.Header>
              <Card.Content class="space-y-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Image (PNG)</label>
                  <div class="flex flex-wrap gap-2 items-center">
                    <input
                      id="card-image"
                      type="file"
                      accept=".png,image/png"
                      class="text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground"
                      onchange={(e) => { setCardImageFile((e.target as HTMLInputElement).files?.[0] ?? null); showCamera = false; }}
                    />
                    <span class="text-muted-foreground text-sm">or</span>
                    <Button type="button" variant="outline" size="sm" onclick={openTakePicture}>
                      Take a picture
                    </Button>
                  </div>
                  {#if showCamera}
                    <div class="mt-3 p-3 rounded-lg border border-border bg-muted/30 space-y-2">
                      <p class="text-sm text-muted-foreground">Allow camera access, then click Capture.</p>
                      {#if cameraError}
                        <p class="text-sm text-destructive">{cameraError}</p>
                      {:else}
                        <div class="relative inline-block rounded-lg overflow-hidden bg-black max-w-xs">
                          <video
                            bind:this={videoEl}
                            autoplay
                            playsinline
                            muted
                            class="block w-full max-h-48 object-cover"
                          ></video>
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
                      <img
                        src={imagePreviewUrl}
                        alt="Preview"
                        class="h-16 w-16 object-contain rounded border border-border"
                      />
                      <span class="text-sm text-muted-foreground">{cardImageFile.name}</span>
                      <Button type="button" variant="ghost" size="sm" onclick={() => { setCardImageFile(null); const i = document.getElementById('card-image') as HTMLInputElement; if (i) i.value = ''; }}>Clear</Button>
                    </div>
                  {/if}
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label for="card-name" class="block text-sm font-medium mb-1">Name *</label>
                    <input id="card-name" type="text" bind:value={cardName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Card name" />
                  </div>
                  <div>
                    <label for="card-number" class="block text-sm font-medium mb-1">Number</label>
                    <input id="card-number" type="text" bind:value={cardNumber} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. 001" />
                  </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                    <label for="card-set-name" class="block text-sm font-medium mb-1">Set name (display)</label>
                    <input id="card-set-name" type="text" bind:value={cardSetName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
                  </div>
                </div>
                <div>
                  <label for="card-quote" class="block text-sm font-medium mb-1">Quote</label>
                  <input id="card-quote" type="text" bind:value={cardQuote} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Optional" />
                </div>
                <div>
                  <label for="card-artwork" class="block text-sm font-medium mb-1">Artwork (credit)</label>
                  <input id="card-artwork" type="text" bind:value={cardArtwork} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Optional" />
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label for="card-types" class="block text-sm font-medium mb-1">Types (comma)</label>
                    <input id="card-types" type="text" bind:value={cardTypes} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label for="card-subtypes" class="block text-sm font-medium mb-1">Subtypes</label>
                    <input id="card-subtypes" type="text" bind:value={cardSubtypes} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label for="card-supertype" class="block text-sm font-medium mb-1">Supertype</label>
                    <input id="card-supertype" type="text" bind:value={cardSupertype} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
                  </div>
                </div>
                <div class="flex gap-2">
                  <Button onclick={addCard} disabled={addingCard || !cardName.trim()}>
                    {addingCard ? 'Adding…' : 'Add card'}
                  </Button>
                  <Button variant="outline" onclick={() => { showAddCard = false; showCamera = false; stopCamera(); }}>Cancel</Button>
                </div>
              </Card.Content>
            </Card.Root>
          {/if}
        {:else}
          <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-8">
            <Card.Content>
              <p class="text-muted-foreground">Select a set to view and add cards.</p>
            </Card.Content>
          </Card.Root>
        {/if}
      </div>
    </div>
  {/if}
</main>
