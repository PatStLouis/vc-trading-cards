<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import TradingCard from '$lib/components/Card.svelte';
  import { fetchApi, fetchAdmin, apiUrl } from '$lib/api';

  const API = apiUrl();

  type CardSet = { id: string; name: string; slug: string; description: string; set_type?: string; card_back_path?: string; created_at: string; updated_at: string };
  type CardItem = {
    id: string; set_id: string; name: string; number: string; rarity: string;
    set_name: string; quote: string; artwork: string; image_path: string;
    photograph?: string; artist?: string; band?: string;
    types: string[]; subtypes: string; supertype: string; created_at: string; updated_at: string;
  };

  let user: { username: string; is_admin: boolean } | null = $state(null);
  let sets: CardSet[] = $state([]);
  let selectedSet: CardSet | null = $state(null);
  let cards: CardItem[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let success = $state('');

  let view: 'sets' | 'cards' = $state('sets');

  let showCreateSet = $state(false);
  let previewCard: CardItem | null = $state(null);
  let issueCard: CardItem | null = $state(null);
  let issueUsers: { discord_sub: string; discord_username: string; wallet_id: string }[] = $state([]);
  let issueUsersLoading = $state(false);
  let issueTargetSub = $state('');
  let issueSubmitting = $state(false);
  let issueError = $state('');

  let newSetName = $state('');
  let newSetDescription = $state('');
  let newSetType = $state('');
  let newSetBackFile: File | null = $state(null);
  let creatingSet = $state(false);

  onMount(async () => {
    try {
      const meRes = await fetchApi('/api/me', { auth: true });
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
      const setsRes = await fetchAdmin('/api/admin/sets');
      if (!setsRes.ok) throw new Error('Failed to load sets');
      const data = await setsRes.json();
      sets = data.sets || [];
      const setParam = $page.url.searchParams.get('set');
      if (setParam) {
        const s = sets.find((x) => x.id === setParam);
        if (s) {
          selectedSet = s;
          await loadCards(s.id);
          view = 'cards';
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  async function loadCards(setId: string) {
    const res = await fetchAdmin(`/api/admin/sets/${setId}/cards`);
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
    newSetType = '';
    newSetBackFile = null;
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
      form.append('set_type', newSetType.trim());
      if (newSetBackFile) form.append('card_back', newSetBackFile);
      const res = await fetchAdmin('/api/admin/sets', {
        method: 'POST',
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

  function imageUrl(path: string): string {
    if (!path) return '';
    const base = API.replace(/\/$/, '');
    return path.startsWith('/') ? `${base}${path}` : `${base}/uploads/${path}`;
  }

  function setBackUrl(set: CardSet): string {
    if (set.card_back_path) return imageUrl(set.card_back_path);
    return '/card-back.svg';
  }

  function closeCreateSet() {
    showCreateSet = false;
  }

  async function deleteSet(setId: string, setName: string) {
    if (!confirm(`Delete the set "${setName}"? This will also delete all cards in the set.`)) return;
    error = '';
    success = '';
    try {
      const res = await fetchAdmin(`/api/admin/sets/${setId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to delete set');
      }
      sets = sets.filter((x) => x.id !== setId);
      if (selectedSet?.id === setId) {
        backToSets();
      }
      success = 'Set deleted.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete set';
    }
  }

  async function deleteCard(c: CardItem) {
    if (!confirm(`Delete the card "${c.name}"?`)) return;
    error = '';
    success = '';
    try {
      const res = await fetchAdmin(`/api/admin/cards/${c.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to delete card');
      }
      if (selectedSet) await loadCards(selectedSet.id);
      success = 'Card deleted.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete card';
    }
  }

  function openIssueModal(c: CardItem) {
    issueCard = c;
    issueTargetSub = '';
    issueError = '';
    issueUsers = [];
    issueUsersLoading = true;
    fetchAdmin('/api/admin/users')
      .then((r) => r.ok ? r.json() : { users: [] })
      .then((data) => { issueUsers = data.users || []; })
      .catch(() => { issueUsers = []; })
      .finally(() => { issueUsersLoading = false; });
  }

  function closeIssueModal() {
    issueCard = null;
    issueTargetSub = '';
    issueError = '';
  }

  async function submitIssue() {
    if (!issueCard || !issueTargetSub.trim()) return;
    issueSubmitting = true;
    issueError = '';
    try {
      const res = await fetchAdmin(`/api/admin/cards/${issueCard.id}/issue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ discord_sub: issueTargetSub.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || (Array.isArray(data.detail) ? data.detail[0]?.msg : 'Failed to issue'));
      }
      success = `Card "${issueCard.name}" issued to user.`;
      closeIssueModal();
    } catch (e) {
      issueError = e instanceof Error ? e.message : 'Failed to issue card';
    } finally {
      issueSubmitting = false;
    }
  }

  // When preview modal is open, lock body scroll and prevent touch from scrolling the background
  $effect(() => {
    if (!previewCard) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const preventTouchScroll = (e: TouchEvent) => e.preventDefault();
    document.addEventListener('touchmove', preventTouchScroll, { passive: false });
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('touchmove', preventTouchScroll);
    };
  });
</script>

<main class="manage-cards-page">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
    <div class="flex items-center gap-2">
      {#if view === 'cards' && selectedSet}
        <Button variant="ghost" size="icon-sm" class="text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700" onclick={backToSets} aria-label="Back to sets">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        </Button>
        <div>
          <h1 class="text-lg font-semibold text-neutral-100">{selectedSet.name}</h1>
          <p class="text-neutral-400 text-sm">{cards.length} cards</p>
        </div>
      {:else}
        <div>
          <h1 class="text-lg font-semibold text-neutral-100">Cards</h1>
          <p class="text-neutral-400 text-sm">Sets and collections</p>
        </div>
      {/if}
    </div>
    <div class="flex gap-2">
      {#if view === 'sets'}
        <Button size="sm" class="h-9 text-sm" onclick={openCreateSet}>New set</Button>
      {:else if selectedSet}
        <a href="/admin/manage-cards/{selectedSet.id}/new">
          <Button size="sm" class="h-9 text-sm">Add card</Button>
        </a>
        <Button variant="outline" size="sm" class="h-9 text-sm border-red-500/50 text-red-400 hover:bg-red-500/10" onclick={() => deleteSet(selectedSet.id, selectedSet.name)}>
          Delete set
        </Button>
      {/if}
    </div>
  </header>

  {#if error}
    <div class="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {/if}
  {#if success}
    <div class="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-emerald-400 text-sm">{success}</div>
  {/if}

  {#if loading}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading…</div>
  {:else if view === 'sets'}
    <ul class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 justify-items-center">
      {#each sets as s}
        <li class="relative group w-full max-w-[280px]">
          <button
            type="button"
            class="cursor-pointer w-full text-left block rounded-[4.55%_/_3.5%] overflow-hidden border border-neutral-700 bg-neutral-800 shadow-lg hover:border-neutral-500 hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:ring-offset-2 focus:ring-offset-neutral-900"
            onclick={() => openSet(s)}
          >
            <div class="aspect-[0.718] w-full rounded-[4.55%_/_3.5%] overflow-hidden bg-neutral-800">
              <img
                src={setBackUrl(s)}
                alt=""
                class="w-full h-full object-cover object-center"
              />
            </div>
          </button>
          <div class="mt-2 px-0.5 text-center">
            <span class="font-medium text-neutral-100 block truncate">{s.name}</span>
            <span class="text-neutral-400 text-xs block truncate">{s.slug}</span>
          </div>
          <button
            type="button"
            class="absolute -top-1 -right-1 p-1.5 rounded-full bg-neutral-800 border border-neutral-600 text-neutral-400 hover:text-red-400 hover:bg-red-500/20 hover:border-red-500/50 opacity-0 group-hover:opacity-100 transition-opacity z-10"
            onclick={(e) => { e.stopPropagation(); e.preventDefault(); deleteSet(s.id, s.name); }}
            aria-label="Delete set {s.name}"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
          </button>
        </li>
      {/each}
    </ul>
    {#if sets.length === 0}
      <div class="py-16 text-center text-neutral-400 rounded-xl border border-dashed border-neutral-700">
        <p class="mb-4 text-sm">No sets yet.</p>
        <Button onclick={openCreateSet}>Create your first set</Button>
      </div>
    {/if}
  {:else if view === 'cards' && selectedSet}
    {#if cards.length === 0}
      <div class="py-16 text-center text-neutral-400 rounded-xl border border-dashed border-neutral-700">
        <p class="mb-4 text-sm">No cards in this set.</p>
        <a href="/admin/manage-cards/{selectedSet.id}/new">
          <Button>Add a card</Button>
        </a>
      </div>
    {:else}
      <ul class="grid gap-5 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {#each cards as c}
          <li class="flex flex-col rounded-xl border border-neutral-700 bg-neutral-800/80 overflow-hidden hover:border-neutral-500 hover:shadow-md transition-all cursor-default">
            <div class="aspect-[0.718] w-full bg-neutral-800 flex items-center justify-center shrink-0">
              {#if c.image_path}
                <img src={imageUrl(c.image_path)} alt={c.name} class="w-full h-full object-contain" />
              {:else}
                <span class="text-neutral-500 text-sm">No image</span>
              {/if}
            </div>
            <div class="p-4 flex flex-col gap-2 flex-1 min-w-0">
              <span class="font-medium text-neutral-100 truncate">{c.name}</span>
              <span class="text-neutral-400 text-sm capitalize">{c.rarity}</span>
              <div class="grid grid-cols-2 gap-2 mt-auto">
                <Button variant="outline" size="sm" class="w-full min-w-0 border-neutral-600 text-neutral-200 hover:bg-neutral-700" onclick={() => (previewCard = c)}>
                  Preview
                </Button>
                <Button variant="outline" size="sm" class="w-full min-w-0 border-primary/50 text-primary hover:bg-primary/10" onclick={() => openIssueModal(c)} title="Issue this card to a user">
                  Issue
                </Button>
                <a href="/admin/manage-cards/{selectedSet.id}/{c.id}/edit" class="min-w-0">
                  <Button variant="outline" size="sm" class="w-full min-w-0 border-neutral-600 text-neutral-200 hover:bg-neutral-700">
                    Edit
                  </Button>
                </a>
                <Button variant="outline" size="sm" class="w-full min-w-0 border-red-500/50 text-red-400 hover:bg-red-500/10" onclick={() => deleteCard(c)} title="Delete card" aria-label="Delete {c.name}">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shrink-0"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
                </Button>
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}

  <!-- Modal: Issue card to user -->
  {#if issueCard}
    <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="issue-card-title" tabindex="-1">
      <div
        class="absolute inset-0 bg-black/60"
        role="button"
        tabindex="0"
        aria-label="Close modal"
        onclick={(e) => { if ((e.target as HTMLElement).closest?.('[data-modal-content]')) return; closeIssueModal(); }}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); closeIssueModal(); } }}></div>
      <div class="relative w-full max-w-md bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-xl p-6 max-h-[90vh] overflow-y-auto" data-modal-content>
        <h2 id="issue-card-title" class="text-lg font-semibold mb-1">Issue card to user</h2>
        <p class="text-muted-foreground text-sm mb-4">Issue “{issueCard.name}” to a registered user. They will see it in their deck immediately.</p>
        {#if issueError}
          <p class="text-red-400 text-sm mb-3">{issueError}</p>
        {/if}
        <div class="space-y-4">
          <div>
            <label for="issue-user" class="block text-sm font-medium mb-1">User</label>
            {#if issueUsersLoading}
              <p class="text-muted-foreground text-sm">Loading users…</p>
            {:else}
              <select
                id="issue-user"
                class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                bind:value={issueTargetSub}
                disabled={issueUsers.length === 0}
              >
                <option value="">Select a user…</option>
                {#each issueUsers as u}
                  <option value={u.discord_sub}>
                    {u.discord_username || u.discord_sub} ({u.wallet_id?.slice(0, 12) ?? '—'}…)
                  </option>
                {/each}
              </select>
              {#if issueUsers.length === 0 && !issueUsersLoading}
                <p class="text-muted-foreground text-xs mt-1">No users yet. Users appear after they log in with Discord.</p>
              {/if}
            {/if}
          </div>
          <div class="flex gap-2 pt-2">
            <Button onclick={submitIssue} disabled={issueSubmitting || !issueTargetSub.trim() || issueUsersLoading}>
              {issueSubmitting ? 'Issuing…' : 'Issue'}
            </Button>
            <Button variant="outline" onclick={closeIssueModal} disabled={issueSubmitting}>Cancel</Button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Modal: Create set -->
  {#if showCreateSet}
    <div class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="create-set-title" tabindex="-1">
      <div
        class="absolute inset-0 bg-black/60"
        role="button"
        tabindex="0"
        aria-label="Close modal"
        onclick={(e) => { if ((e.target as HTMLElement).closest?.('[data-modal-content]')) return; closeCreateSet(); }}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); closeCreateSet(); } }}></div>
      <div class="relative w-full max-w-md bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-xl p-6 max-h-[90vh] overflow-y-auto" data-modal-content>
        <h2 id="create-set-title" class="text-lg font-semibold mb-1">Create set</h2>
        <p class="text-muted-foreground text-sm mb-4">Slug is derived from the name.</p>
        <div class="space-y-4">
          <div>
            <label for="set-name" class="block text-sm font-medium mb-1">Name</label>
            <input id="set-name" type="text" bind:value={newSetName} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. Genesis" />
          </div>
          <div>
            <label for="set-type" class="block text-sm font-medium mb-1">Set type</label>
            <input id="set-type" type="text" bind:value={newSetType} class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. Trading Card, Collectible" />
          </div>
          <div>
            <label for="set-desc" class="block text-sm font-medium mb-1">Description (optional)</label>
            <textarea id="set-desc" bind:value={newSetDescription} rows="2" class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Optional"></textarea>
          </div>
          <div>
            <label for="set-back" class="block text-sm font-medium mb-1">Card back image (optional)</label>
            <input
              id="set-back"
              type="file"
              accept=".png,.svg,.jpg,.jpeg,.webp,image/png,image/svg+xml,image/jpeg,image/webp"
              class="w-full text-sm file:mr-2 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-primary file:text-primary-foreground"
              onchange={(e) => { newSetBackFile = (e.target as HTMLInputElement).files?.[0] ?? null; }}
            />
            <p class="text-muted-foreground text-xs mt-0.5">PNG, SVG, JPG, or WebP. Used as the back of cards in this set.</p>
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

  <!-- Modal: Preview (holographic card) -->
  {#if previewCard}
    <div
      class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 overflow-hidden touch-none"
      role="dialog"
      aria-modal="true"
      aria-label="Card preview"
      tabindex="-1"
      onclick={() => (previewCard = null)}
      onkeydown={(e) => { if (e.key === 'Escape') previewCard = null; }}>
      <div class="max-w-[min(280px,95vw)]" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
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
          back={selectedSet ? setBackUrl(selectedSet) : '/card-back.svg'}
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
    width: 100%;
  }
</style>
