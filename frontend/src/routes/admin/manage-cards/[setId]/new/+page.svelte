<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import TradingCard from '$lib/components/Card.svelte';

  const API = import.meta.env.VITE_API_URL ?? '';

  type CardSet = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string; created_at: string; updated_at: string };

  const setId = $derived($page.params.setId);

  let set: CardSet | null = $state(null);
  let loading = $state(true);
  let error = $state('');
  let submitting = $state(false);

  let name = $state('');
  let rarity = $state('common');
  let quote = $state('');
  let photograph = $state('');
  let artist = $state('');
  let band = $state('');
  let imageFile: File | null = $state(null);
  let imagePreviewUrl = $state('');

  let showCamera = $state(false);
  let cameraError = $state('');
  let videoEl: HTMLVideoElement | null = $state(null);
  let mediaStream: MediaStream | null = $state(null);

  function setImageFile(file: File | null) {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    imagePreviewUrl = '';
    imageFile = file;
    if (file) imagePreviewUrl = URL.createObjectURL(file);
  }

  function openCamera() {
    setImageFile(null);
    cameraError = '';
    showCamera = true;
  }

  function stopCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (videoEl) videoEl.srcObject = null;
  }

  function startCamera() {
    if (mediaStream || !videoEl) return;
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
        mediaStream = stream;
        if (videoEl) {
          videoEl.srcObject = stream;
          videoEl.play().catch(() => {});
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
    canvas.toBlob((blob) => {
      if (!blob) return;
      setImageFile(new File([blob], 'capture.png', { type: 'image/png' }));
      stopCamera();
      showCamera = false;
    }, 'image/png');
  }

  $effect(() => {
    if (showCamera && videoEl) {
      startCamera();
      return () => stopCamera();
    }
  });

  onMount(async () => {
    if (!setId) {
      goto('/admin/manage-cards');
      return;
    }
    try {
      const res = await fetch(`${API}/api/admin/sets/${setId}`, { credentials: 'include' });
      if (res.status === 404) {
        goto('/admin/manage-cards');
        return;
      }
      if (!res.ok) throw new Error('Failed to load set');
      set = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load set';
    } finally {
      loading = false;
    }
  });

  async function submit() {
    if (!set || !name.trim()) return;
    submitting = true;
    error = '';
    try {
      const form = new FormData();
      form.append('name', name.trim());
      form.append('number', '');
      form.append('rarity', rarity);
      form.append('set_name', set.name);
      form.append('quote', quote.trim());
      form.append('artwork', '');
      form.append('photograph', photograph.trim());
      form.append('artist', artist.trim());
      form.append('band', band.trim());
      form.append('types', 'TradingCard');
      form.append('subtypes', 'trading-cards');
      form.append('supertype', 'trading-card');
      if (imageFile) form.append('image', imageFile);
      const res = await fetch(`${API}/api/admin/sets/${set.id}/cards`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create card');
      }
      goto(`/admin/manage-cards?set=${set.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create card';
    } finally {
      submitting = false;
    }
  }

  function backUrl(): string {
    if (set?.card_back_path) {
      const base = API.replace(/\/$/, '');
      return base ? `${base}/uploads/${set.card_back_path}` : `/uploads/${set.card_back_path}`;
    }
    return '/card-back.svg';
  }

  const rarities = [
    { value: 'common', label: 'Common (no foil)' },
    { value: 'uncommon', label: 'Uncommon' },
    { value: 'rare', label: 'Rare' },
    { value: 'reverse-holo', label: 'Reverse Holo' },
    { value: 'rare-holo', label: 'Rare Holo (prismatic)' },
    { value: 'double-rare', label: 'Double Rare (beams)' },
    { value: 'illustration-rare', label: 'Illustration Rare (beams)' },
    { value: 'legendary', label: 'Legendary (gold)' },
    { value: 'promo', label: 'Promo (gold)' },
    { value: 'ultra-rare', label: 'Ultra Rare (cosmos)' },
    { value: 'secret-rare', label: 'Secret Rare (cosmos)' },
    { value: 'galaxy', label: 'Galaxy (cosmos)' },
    { value: 'special', label: 'Special (beams)' },
  ];
</script>

<svelte:head>
  <title>New card · {set?.name ?? 'Cards'}</title>
</svelte:head>

<div class="card-builder-page max-w-4xl mx-auto">
  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if !set}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error || 'Set not found.'}</div>
  {:else}
    <div class="mb-6 flex items-center gap-2 text-sm">
      <a href="/admin/manage-cards" class="text-neutral-400 hover:text-white">Cards</a>
      <span class="text-neutral-600">/</span>
      <a href="/admin/manage-cards?set={set.id}" class="text-neutral-400 hover:text-white">{set.name}</a>
      <span class="text-neutral-600">/</span>
      <span class="text-white font-medium">New card</span>
    </div>

    <div class="grid gap-6 lg:grid-cols-[auto_280px] lg:grid-flow-col lg:place-content-start">
      <!-- Inputs: left column -->
      <section class="space-y-4 lg:col-start-1 lg:row-start-1 max-w-sm">
        <h1 class="text-lg font-semibold text-white">Card designer</h1>

        {#if error}
          <div class="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-red-400 text-xs">{error}</div>
        {/if}

        <div class="rounded-lg border border-neutral-700 bg-neutral-800/80 p-4 space-y-3">
          <div>
            <label for="card-name" class="block text-xs font-medium text-neutral-200 mb-1">Name *</label>
            <input
              id="card-name"
              type="text"
              bind:value={name}
              placeholder="Card name"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
          </div>

          <div>
            <label for="card-rarity" class="block text-xs font-medium text-neutral-200 mb-1">Rarity</label>
            <select
              id="card-rarity"
              bind:value={rarity}
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-neutral-500">
              {#each rarities as r}
                <option value={r.value}>{r.label}</option>
              {/each}
            </select>
          </div>

          <div>
            <label for="card-quote" class="block text-xs font-medium text-neutral-200 mb-1">Quote</label>
            <input
              id="card-quote"
              type="text"
              bind:value={quote}
              placeholder="Quote on the card"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
          </div>

          <div>
            <label for="card-photograph" class="block text-xs font-medium text-neutral-200 mb-1">Photographer</label>
            <input
              id="card-photograph"
              type="text"
              bind:value={photograph}
              placeholder="Photographer credit"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
          </div>

          <div>
            <label for="card-artist" class="block text-xs font-medium text-neutral-200 mb-1">Artist</label>
            <input
              id="card-artist"
              type="text"
              bind:value={artist}
              placeholder="Artist on the card"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
          </div>

          <div>
            <label for="card-band" class="block text-xs font-medium text-neutral-200 mb-1">Band</label>
            <input
              id="card-band"
              type="text"
              bind:value={band}
              placeholder="Band"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
          </div>

          <div>
            <label class="block text-xs font-medium text-neutral-200 mb-1">Set</label>
            <input
              type="text"
              value={set.name}
              disabled
              class="w-full rounded-md border border-neutral-700 bg-neutral-800/50 px-3 py-2 text-sm text-neutral-400 cursor-not-allowed" />
          </div>

          <div>
            <label class="block text-xs font-medium text-neutral-200 mb-1">Image (PNG)</label>
            <div class="flex flex-wrap gap-2 items-center">
              <input
                type="file"
                accept=".png,image/png"
                class="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:bg-neutral-600 file:text-white file:cursor-pointer"
                onchange={(e) => {
                  setImageFile((e.target as HTMLInputElement).files?.[0] ?? null);
                  showCamera = false;
                }} />
              <span class="text-neutral-500 text-xs">or</span>
              <Button variant="outline" size="sm" class="h-7 text-xs border-neutral-600 text-neutral-200 hover:bg-neutral-700" onclick={openCamera}>
                Take picture
              </Button>
            </div>
            {#if showCamera}
              <div class="mt-3 p-3 rounded-lg border border-neutral-700 bg-neutral-800 space-y-2">
                {#if cameraError}
                  <p class="text-xs text-red-400">{cameraError}</p>
                {:else}
                  <div class="rounded-lg overflow-hidden bg-black min-h-[160px]">
                    <video bind:this={videoEl} autoplay playsinline muted class="block w-full min-h-[160px] object-cover"></video>
                  </div>
                  <div class="flex gap-2">
                    <Button size="sm" class="h-7 text-xs" onclick={capturePhoto}>Capture</Button>
                    <Button variant="outline" size="sm" class="h-7 text-xs border-neutral-600 text-neutral-200" onclick={() => { stopCamera(); showCamera = false; }}>Cancel</Button>
                  </div>
                {/if}
              </div>
            {/if}
            {#if imageFile && !showCamera}
              <div class="mt-2 flex items-center gap-2 p-2 rounded-md border border-neutral-700 bg-neutral-800/50">
                <img src={imagePreviewUrl} alt="Preview" class="h-12 w-12 object-contain rounded border border-neutral-600" />
                <span class="text-xs text-neutral-400 truncate flex-1">{imageFile.name}</span>
                <Button variant="ghost" size="sm" class="h-7 text-xs text-neutral-400 hover:text-white" onclick={() => setImageFile(null)}>Clear</Button>
              </div>
            {/if}
          </div>
        </div>

        <div class="flex gap-2">
          <Button size="sm" class="h-8 text-xs" onclick={submit} disabled={submitting || !name.trim()}>
            {submitting ? 'Creating…' : 'Create card'}
          </Button>
          <Button variant="outline" size="sm" class="h-8 text-xs border-neutral-600 text-neutral-200 hover:bg-neutral-700" href="/admin/manage-cards?set={set.id}">
            Cancel
          </Button>
        </div>
      </section>

      <!-- Preview: right column -->
      <section class="lg:col-start-2 lg:row-start-1 lg:sticky lg:top-6">
        <h2 class="text-sm font-medium text-neutral-400 mb-3">Preview</h2>
        <div class="flex justify-center">
          <div class="w-full max-w-[280px]">
            <TradingCard
              id="preview"
              name={name || 'Card name'}
              number=""
              set={set.name}
              types={['TradingCard']}
              subtypes="trading-cards"
              supertype="trading-card"
              rarity={rarity}
              img={imagePreviewUrl}
              back={backUrl()}
            />
          </div>
        </div>
      </section>
    </div>
  {/if}
</div>
