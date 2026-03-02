<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Card from '$lib/components/Card.svelte';
  import { activeCard } from '$lib/stores/activeCard';

  let user: { username: string; wallet_id: string } | null = null;
  let cards: Array<Record<string, unknown>> = [];
  let loading = true;
  let error = '';

  const API = typeof window !== 'undefined' ? '' : (import.meta.env.VITE_API_URL || '');

  onMount(async () => {
    try {
      const [meRes, credsRes] = await Promise.all([
        fetch(`${API || ''}/api/me`, { credentials: 'include' }),
        fetch(`${API || ''}/api/wallet/credentials`, { credentials: 'include' })
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

  async function logout() {
    await fetch(`${API || ''}/auth/logout`, { method: 'POST', credentials: 'include' });
    goto('/');
  }
</script>

<main class="wallet-page">
  <header class="wallet-header">
    <h1>My collection</h1>
    {#if user}
      <p class="user">@{user.username} · <span class="wallet-id">{user.wallet_id?.slice(0, 12)}…</span></p>
      <button class="btn btn-outline" onclick={logout}>Log out</button>
    {/if}
  </header>

  {#if loading}
    <p class="loading">Loading your cards…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if cards.length === 0}
    <p class="empty">No cards in your wallet yet. Credentials issued to this wallet will appear here.</p>
  {:else}
    <section class="card-grid">
      {#each cards as card (card.id)}
        <Card
          id={card.id}
          name={String(card.name ?? 'Card')}
          number={String(card.number ?? '')}
          set={String(card.set ?? '')}
          types={Array.isArray(card.types) ? card.types : [card.types].filter(Boolean)}
          subtypes={String(card.subtypes ?? 'trading-cards')}
          supertype={String(card.supertype ?? 'trading-card')}
          rarity={String(card.rarity ?? 'common')}
          img={String(card.image_url ?? card.artwork ?? '')}
        />
      {/each}
    </section>
  {/if}
</main>

<style>
  .wallet-page {
    padding: 2rem 1rem;
  }
  .wallet-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 1rem;
  }
  .wallet-header h1 {
    margin: 0;
    font-size: 1.5rem;
  }
  .user {
    margin: 0;
    opacity: 0.9;
    font-size: 0.95rem;
  }
  .wallet-id {
    font-family: monospace;
    font-size: 0.85em;
  }
  .btn-outline {
    margin-left: auto;
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.3);
    color: var(--text-light);
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .btn-outline:hover {
    background: rgba(255,255,255,0.05);
  }
  .loading, .error, .empty {
    text-align: center;
    padding: 2rem;
    opacity: 0.9;
  }
  .error { color: #f44336; }
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 2rem;
    padding: 1rem 0;
  }
</style>
