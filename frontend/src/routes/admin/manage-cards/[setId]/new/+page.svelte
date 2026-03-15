<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import TradingCard from '$lib/components/Card.svelte';
  import { fetchAdmin, apiUrl } from '$lib/api';

  const API = apiUrl();

  type CardSet = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string; created_at: string; updated_at: string };

  const setId = $derived($page.params.setId);

  let set: CardSet | null = $state(null);
  let loading = $state(true);
  let error = $state('');
  let submitting = $state(false);

  let rarity = $state('common');
  let quote = $state('');
  let photograph = $state('');
  let artist = $state('');
  let band = $state('');
  /** Full card number e.g. "1/57" */
  let number = $state('');
  let imageFile: File | null = $state(null);
  let imagePreviewUrl = $state('');
  let analyzing = $state(false);
  let analysisMessage = $state('');
  let lastAnalysis = $state<Record<string, unknown> | null>(null);
  let isDragging = $state(false);
  let fileInputEl: HTMLInputElement | null = $state(null);

  const ACCEPT_TYPES = ['image/png', 'image/jpeg', 'image/jpg'];
  function isImageFile(file: File): boolean {
    const t = (file.type || '').toLowerCase();
    return ACCEPT_TYPES.includes(t) || /\.(png|jpe?g)$/i.test(file.name || '');
  }

  function setImageFile(file: File | null) {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    imagePreviewUrl = '';
    imageFile = file;
    analysisMessage = '';
    lastAnalysis = null;
    quote = '';
    photograph = '';
    artist = '';
    band = '';
    number = '';
    if (file) imagePreviewUrl = URL.createObjectURL(file);
  }

  function onFileChosen(file: File | null) {
    if (file && !isImageFile(file)) return;
    setImageFile(file);
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) onFileChosen(file);
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    isDragging = true;
  }

  function handleDragLeave() {
    isDragging = false;
  }

  function triggerFileInput() {
    fileInputEl?.click();
  }

  /** Send current image to backend for analysis; updates lastAnalysis and pre-fills suggested fields. */
  async function runAnalyse() {
    if (!imageFile) return;
    await analyzeImageAndApply(imageFile);
  }

  async function analyzeImageAndApply(file: File) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (ext !== 'png' && ext !== 'jpg' && ext !== 'jpeg') return;
    analyzing = true;
    analysisMessage = '';
    try {
      const form = new FormData();
      form.append('image', file);
      const res = await fetchAdmin('/api/admin/analyze-card-image', { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        analysisMessage = err.detail || 'Analysis failed';
        return;
      }
      const data = await res.json();
      const s = data.suggested || {};
      if (s.name && !artist.trim()) artist = s.name;
      if (s.quote && !quote.trim()) quote = s.quote;
      if (s.photograph && !photograph.trim()) photograph = s.photograph;
      if ((s.number != null || s.total_in_set != null) && !number.trim()) {
        const n = (s.number ?? '').toString().trim();
        const t = (s.total_in_set ?? '').toString().trim();
        number = t ? `${n}/${t}` : n;
      }
      lastAnalysis = data;
      if (Object.keys(s).length > 0) analysisMessage = 'Suggestions applied from image.';
      else if (data.width && data.height) analysisMessage = `Image: ${data.format} ${data.width}×${data.height}.`;
      if (data.ocr_error) analysisMessage = (analysisMessage ? analysisMessage + ' ' : '') + `OCR: ${data.ocr_error}`;
    } catch {
      analysisMessage = 'Could not analyze image.';
    } finally {
      analyzing = false;
    }
  }

  onMount(async () => {
    if (!setId) {
      goto('/admin/manage-cards');
      return;
    }
    try {
      const res = await fetchAdmin(`/api/admin/sets/${setId}`);
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
    if (!set || !imageFile) return;
    submitting = true;
    error = '';
    try {
      const cardId = await generateCardId();
      const form = new FormData();
      form.append('card_id', cardId);
      form.append('number', number.trim());
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
      const res = await fetchAdmin(`/api/admin/sets/${set.id}/cards`, {
        method: 'POST',
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

  /** Generate a unique card_id: hash of set+number+artist+quote+photo+band+rarity, or UUID if empty. */
  async function generateCardId(): Promise<string> {
    const payload = [set?.id ?? '', number, artist, quote, photograph, band, rarity].join('|');
    if (!payload.replace(/\|/g, '').trim()) return crypto.randomUUID();
    const encoder = new TextEncoder();
    const buf = await crypto.subtle.digest('SHA-256', encoder.encode(payload));
    const arr = new Uint8Array(buf);
    return Array.from(arr)
      .slice(0, 16)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
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

    <div class="card-designer-grid">
      <!-- Inputs: left column -->
      <section class="card-designer-form">
        <h1 class="text-lg font-semibold text-white">Card designer</h1>

        {#if error}
          <div class="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-red-400 text-xs">{error}</div>
        {/if}

        <div class="rounded-lg border border-neutral-700 bg-neutral-800/80 p-4 space-y-3 card-designer-panel">
          <div class="card-designer-rarity-row">
            <label for="card-rarity" class="text-xs font-medium text-neutral-200">Rarity</label>
            <select
              id="card-rarity"
              bind:value={rarity}
              class="rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-neutral-500">
              {#each rarities as r}
                <option value={r.value}>{r.label}</option>
              {/each}
            </select>
          </div>

          <div class="card-designer-image-block">
            <label class="block text-xs font-medium text-neutral-200 mb-1">Image (PNG or JPEG)</label>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,image/png,image/jpeg"
              class="sr-only"
              bind:this={fileInputEl}
              onchange={(e) => {
                onFileChosen((e.target as HTMLInputElement).files?.[0] ?? null);
                (e.target as HTMLInputElement).value = '';
              }}
            />
            <button
              type="button"
              class="image-drop-zone"
              class:is-dragging={isDragging}
              class:has-image={!!imageFile}
              onclick={triggerFileInput}
              ondrop={handleDrop}
              ondragover={handleDragOver}
              ondragleave={handleDragLeave}
              ondragenter={handleDragOver}
            >
              {#if imageFile}
                <img src={imagePreviewUrl} alt="Preview" class="image-drop-preview" />
                <span class="image-drop-change">Click or drag to replace</span>
              {:else}
                <span class="image-drop-text">Drag image here or click to upload</span>
                <span class="image-drop-hint">PNG or JPEG</span>
              {/if}
            </button>
            {#if analyzing}
              <div class="mt-3 flex items-center gap-2 text-xs text-neutral-400">
                <span class="analyzing-dots">
                  <span>.</span><span>.</span><span>.</span>
                </span>
                <span>Analysing image</span>
              </div>
            {:else if analysisMessage}
              <p class="mt-2 text-xs {analysisMessage.includes('failed') || analysisMessage.includes('Could not') ? 'text-amber-400/90' : 'text-emerald-400/90'}">{analysisMessage}</p>
            {/if}
            {#if imageFile}
              <div class="mt-2 flex items-center gap-2 flex-wrap">
                <Button variant="ghost" size="sm" class="h-7 text-xs text-neutral-400 hover:text-white" onclick={(e) => { e.stopPropagation(); setImageFile(null); }}>Clear image</Button>
              </div>
              <div class="mt-2 flex items-center gap-2 flex-wrap">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  class="h-7 text-xs border-neutral-600 text-neutral-300 hover:bg-neutral-700"
                  onclick={runAnalyse}
                  disabled={analyzing}
                >
                  {analyzing ? 'Analysing…' : 'Analyse'}
                </Button>
                {#if !lastAnalysis && !analyzing}
                  <span class="text-xs text-neutral-500">Extract artist, quote, photographer, number (e.g. 1/57) from image</span>
                {/if}
              </div>
            {#if lastAnalysis && !lastAnalysis.error}
              <div class="card-designer-details-card">
                <p class="text-xs font-medium text-neutral-300">Image details</p>
                <dl class="text-xs text-neutral-400 space-y-1">
                  <div class="flex gap-2">
                    <dt class="text-neutral-500">Format</dt>
                    <dd>{lastAnalysis.format ?? '—'} {lastAnalysis.width && lastAnalysis.height ? ` · ${lastAnalysis.width}×${lastAnalysis.height}` : ''}</dd>
                  </div>
                  <div class="flex gap-2">
                    <dt class="text-neutral-500">EXIF</dt>
                    <dd>{lastAnalysis.has_exif ? 'Yes' : 'No'}</dd>
                  </div>
                  <div class="flex gap-2">
                    <dt class="text-neutral-500">ICC profile</dt>
                    <dd>{lastAnalysis.has_icc ? 'Yes' : 'No'}</dd>
                  </div>
                  {#if lastAnalysis.suggested && typeof lastAnalysis.suggested === 'object' && Object.keys(lastAnalysis.suggested as object).length > 0}
                    <div class="pt-1 mt-1 border-t border-neutral-700">
                      <dt class="text-neutral-500 mb-1">Card Details</dt>
                      <dd class="space-y-0.5">
                        {#each Object.entries(lastAnalysis.suggested as Record<string, string>) as [key, value]}
                          {#if value}
                            <div class="flex gap-2">
                              <span class="text-neutral-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                              <span class="text-neutral-300 truncate max-w-[180px]" title={value}>{value}</span>
                            </div>
                          {/if}
                        {/each}
                      </dd>
                    </div>
                  {/if}
                </dl>
              </div>
            {/if}
            {/if}
          </div>
        </div>

        <div class="flex gap-2">
          <Button size="sm" class="h-8 text-xs" onclick={submit} disabled={submitting || !imageFile}>
            {submitting ? 'Creating…' : 'Create card'}
          </Button>
          <Button variant="outline" size="sm" class="h-8 text-xs border-neutral-600 text-neutral-200 hover:bg-neutral-700" href="/admin/manage-cards?set={set.id}">
            Cancel
          </Button>
        </div>
      </section>

      <!-- Preview: right column -->
      <section class="card-designer-preview">
        <h2 class="text-sm font-medium text-neutral-400 mb-3">Preview</h2>
        <div class="card-designer-preview-slot">
          <div class="card-designer-preview-inner">
            <TradingCard
              id="preview"
              name={number && artist ? `${number} · ${artist}` : number || artist || 'Card'}
              number={number}
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

<style>
  .image-drop-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    width: 100%;
    height: 200px;
    min-height: 200px;
    padding: 1rem;
    border: 2px dashed var(--zone-border, rgb(64 64 64));
    border-radius: 0.5rem;
    background: var(--zone-bg, rgb(38 38 38 / 0.6));
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    box-sizing: border-box;
  }
  .image-drop-zone:hover {
    --zone-border: rgb(82 82 82);
    --zone-bg: rgb(38 38 38 / 0.8);
  }
  .image-drop-zone.is-dragging {
    --zone-border: rgb(96 165 250);
    --zone-bg: rgb(59 130 246 / 0.15);
  }
  .image-drop-zone.has-image {
    padding: 0;
    position: relative;
    overflow: hidden;
    border-style: solid;
    height: 200px;
    min-height: 200px;
  }
  .image-drop-preview {
    width: 100%;
    height: 200px;
    object-fit: contain;
    background: rgb(23 23 23);
  }
  .image-drop-change {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgb(0 0 0 / 0.5);
    color: rgb(229 229 229);
    font-size: 0.75rem;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .image-drop-zone.has-image:hover .image-drop-change {
    opacity: 1;
  }
  .image-drop-text {
    font-size: 0.8125rem;
    color: rgb(212 212 212);
  }
  .image-drop-hint {
    font-size: 0.6875rem;
    color: rgb(115 115 115);
  }

  .card-designer-grid {
    display: grid;
    gap: 1.5rem;
    grid-template-columns: 1fr;
    align-content: start;
  }
  @media (min-width: 1024px) {
    .card-designer-grid {
      grid-template-columns: 320px 280px;
      gap: 2rem;
    }
  }

  .card-designer-form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-width: 0;
  }
  @media (min-width: 1024px) {
    .card-designer-form {
      width: 320px;
    }
  }

  .card-designer-panel {
    width: 100%;
    min-width: 0;
  }

  .card-designer-rarity-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .card-designer-image-block {
    width: 100%;
    min-width: 0;
  }

  .card-designer-details-card {
    margin-top: 0.75rem;
    padding: 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid rgb(64 64 64);
    background: rgb(38 38 38 / 0.7);
    min-height: 80px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .card-designer-preview {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  @media (min-width: 1024px) {
    .card-designer-preview {
      width: 280px;
      position: sticky;
      top: 1.5rem;
    }
  }

  .card-designer-preview-slot {
    width: 100%;
    aspect-ratio: 660 / 921;
    max-width: 280px;
    margin: 0 auto;
  }
  @media (min-width: 1024px) {
    .card-designer-preview-slot {
      width: 280px;
      max-width: none;
      margin: 0;
    }
  }

  .card-designer-preview-inner {
    width: 100%;
    height: 100%;
  }
  .card-designer-preview-inner :global(.card) {
    width: 100%;
    height: 100%;
  }
  .card-designer-preview-inner :global(.card__rotator),
  .card-designer-preview-inner :global(.card__translater) {
    width: 100%;
    height: 100%;
  }

  .analyzing-dots {
    display: inline-flex;
    gap: 2px;
    align-items: center;
  }
  .analyzing-dots span {
    animation: analyzing-dot 0.6s ease-in-out infinite both;
  }
  .analyzing-dots span:nth-child(1) { animation-delay: 0s; }
  .analyzing-dots span:nth-child(2) { animation-delay: 0.2s; }
  .analyzing-dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes analyzing-dot {
    0%, 80%, 100% { opacity: 0.35; transform: scale(0.9); }
    40% { opacity: 1; transform: scale(1.15); }
  }
</style>
