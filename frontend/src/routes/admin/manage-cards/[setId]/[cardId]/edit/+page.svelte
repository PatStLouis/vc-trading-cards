<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import TradingCard from '$lib/components/Card.svelte';
  import { fetchAdmin, apiUrl } from '$lib/api';

  const API = apiUrl();

  type CardSet = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string; created_at: string; updated_at: string };
  type CardItem = {
    id: string; set_id: string; name: string; number: string; rarity: string;
    set_name: string; quote: string; artwork: string; image_path: string;
    photograph?: string; artist?: string; band?: string;
    types: string[]; subtypes: string; supertype: string; created_at: string; updated_at: string;
  };

  const setId = $derived($page.params.setId);
  const cardId = $derived($page.params.cardId);

  let set: CardSet | null = $state(null);
  let card: CardItem | null = $state(null);
  let loading = $state(true);
  let error = $state('');
  let submitting = $state(false);

  let name = $state('');
  let rarity = $state('common');
  let quote = $state('');
  let photograph = $state('');
  let artist = $state('');
  let band = $state('');
  let number = $state('');
  let imageFile: File | null = $state(null);
  let imagePreviewUrl = $state('');
  let currentImageUrl = $state('');
  let drawNumberOnImage = $state(false);

  let showCamera = $state(false);
  let cameraError = $state('');
  let videoEl: HTMLVideoElement | null = $state(null);
  let mediaStream: MediaStream | null = $state(null);

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = API.replace(/\/$/, '');
    return path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }

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
    if (!setId || !cardId) {
      goto('/admin/manage-cards');
      return;
    }
    try {
      const [setRes, cardRes] = await Promise.all([
        fetchAdmin(`/api/admin/sets/${setId}`),
        fetchAdmin(`/api/admin/cards/${cardId}`),
      ]);
      if (setRes.status === 404 || cardRes.status === 404) {
        goto('/admin/manage-cards');
        return;
      }
      if (!setRes.ok) throw new Error('Failed to load set');
      if (!cardRes.ok) throw new Error('Failed to load card');
      set = await setRes.json();
      card = await cardRes.json();
      name = card.name ?? '';
      rarity = card.rarity ?? 'common';
      quote = card.quote ?? '';
      photograph = card.photograph ?? '';
      artist = card.artist ?? '';
      band = card.band ?? '';
      number = card.number ?? '';
      currentImageUrl = card.image_path ? imageUrl(card.image_path) : '';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  async function submit() {
    if (!set || !card || !name.trim()) return;
    submitting = true;
    error = '';
    try {
      let fileToUpload: File | null = imageFile;
      if (imageFile && drawNumberOnImage && number.trim()) {
        const composited = await drawNumberOnImageCanvas(imageFile, number.trim());
        if (composited) fileToUpload = composited;
      }
      const form = new FormData();
      form.append('name', name.trim());
      form.append('number', number.trim());
      form.append('rarity', rarity);
      form.append('set_name', set.name);
      form.append('quote', quote.trim());
      form.append('artwork', card.artwork ?? '');
      form.append('photograph', photograph.trim());
      form.append('artist', artist.trim());
      form.append('band', band.trim());
      form.append('types', 'TradingCard');
      form.append('subtypes', card.subtypes ?? 'trading-cards');
      form.append('supertype', card.supertype ?? 'trading-card');
      if (fileToUpload) form.append('image', fileToUpload);
      const res = await fetchAdmin(`/api/admin/cards/${card.id}`, {
        method: 'PUT',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update card');
      }
      goto(`/admin/manage-cards?set=${set.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to update card';
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

  /** Draw the card number onto the image at bottom-right; returns a new PNG File for upload. */
  function drawNumberOnImageCanvas(file: File, numberText: string): Promise<File | null> {
    if (!numberText.trim()) return Promise.resolve(null);
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(null);
          return;
        }
        ctx.drawImage(img, 0, 0);
        const padX = Math.max(12, img.width * 0.04);
        const padY = Math.max(12, img.height * 0.04);
        const fontSize = Math.max(14, Math.round(img.height * 0.035));
        ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'bottom';
        const x = img.width - padX;
        const y = img.height - padY;
        ctx.strokeStyle = 'rgba(0,0,0,0.9)';
        ctx.lineWidth = Math.max(2, fontSize / 8);
        ctx.strokeText(numberText.trim(), x, y);
        ctx.fillStyle = 'rgba(255,255,255,0.95)';
        ctx.fillText(numberText.trim(), x, y);
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              resolve(null);
              return;
            }
            const name = file.name.replace(/\.[^.]+$/, '') + '.png';
            resolve(new File([blob], name, { type: 'image/png' }));
          },
          'image/png',
          0.92
        );
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(null);
      };
      img.src = url;
    });
  }

  const displayImg = $derived(imagePreviewUrl || currentImageUrl);

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
  <title>Edit {card?.name ?? 'card'} · {set?.name ?? 'Cards'}</title>
</svelte:head>

<div class="card-builder-page max-w-4xl mx-auto">
  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if !set || !card}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error || 'Set or card not found.'}</div>
  {:else}
    <div class="mb-6 flex items-center gap-2 text-sm">
      <a href="/admin/manage-cards" class="text-neutral-400 hover:text-white">Cards</a>
      <span class="text-neutral-600">/</span>
      <a href="/admin/manage-cards?set={set.id}" class="text-neutral-400 hover:text-white">{set.name}</a>
      <span class="text-neutral-600">/</span>
      <span class="text-white font-medium">Edit card</span>
    </div>

    <div class="grid gap-6 lg:grid-cols-[auto_280px] lg:grid-flow-col lg:place-content-start">
      <section class="space-y-4 lg:col-start-1 lg:row-start-1 max-w-sm">
        <h1 class="text-lg font-semibold text-white">Edit card</h1>

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
            <label for="card-number" class="block text-xs font-medium text-neutral-200 mb-1">Card number</label>
            <input
              id="card-number"
              type="text"
              bind:value={number}
              placeholder="e.g. 1"
              class="w-full rounded-md border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
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
            <label class="block text-xs font-medium text-neutral-200 mb-1">Image (PNG or JPEG)</label>
            <p class="text-neutral-500 text-xs mb-1">Leave empty to keep current image.</p>
            <div class="flex flex-wrap gap-2 items-center">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,image/png,image/jpeg"
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
              <label class="mt-2 flex items-center gap-2 cursor-pointer">
                <input type="checkbox" bind:checked={drawNumberOnImage} class="rounded border-neutral-600 bg-neutral-800 text-neutral-200 focus:ring-neutral-500" />
                <span class="text-xs text-neutral-300">Draw card number on image (bottom-right)</span>
              </label>
            {/if}
          </div>
        </div>

        <div class="flex gap-2">
          <Button size="sm" class="h-8 text-xs" onclick={submit} disabled={submitting || !name.trim()}>
            {submitting ? 'Saving…' : 'Save changes'}
          </Button>
          <Button variant="outline" size="sm" class="h-8 text-xs border-neutral-600 text-neutral-200 hover:bg-neutral-700" href="/admin/manage-cards?set={set.id}">
            Cancel
          </Button>
        </div>
      </section>

      <section class="lg:col-start-2 lg:row-start-1 lg:sticky lg:top-6">
        <h2 class="text-sm font-medium text-neutral-400 mb-3">Preview</h2>
        <div class="flex justify-center">
          <div class="w-full max-w-[280px]">
            <TradingCard
              id={card.id}
              name={name || 'Card name'}
              number={number}
              set={set.name}
              types={['TradingCard']}
              subtypes={card.subtypes ?? 'trading-cards'}
              supertype={card.supertype ?? 'trading-card'}
              rarity={rarity}
              img={displayImg}
              back={backUrl()}
            />
          </div>
        </div>
      </section>
    </div>
  {/if}
</div>
