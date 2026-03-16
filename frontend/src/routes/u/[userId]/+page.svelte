<script lang="ts">
  import { page } from '$app/stores';
  import { fetchApi, apiUrl } from '$lib/api';
  import { onMount } from 'svelte';

  const API = apiUrl();
  function cardImageUrl(card: Card): string {
    const u = card?.image_path ?? card?.artwork ?? '';
    if (!u) return '';
    const base = (API || '').replace(/\/$/, '');
    return u.startsWith('http') ? u : u.startsWith('/') ? `${base}${u}` : `${base}/uploads/${u}`;
  }

  type PublicUser = {
    user_id: string;
    username: string | null;
    poser_username: string | null;
    avatar_url?: string | null;
    collection_count: number;
    featured_card_ids?: string[];
    profile_headline?: string | null;
    profile_bio?: string | null;
    profile_song_url?: string | null;
    profile_song_upload_url?: string | null;
    profile_accent_color?: string | null;
  };

  function isYouTubeUrl(url: string): boolean {
    if (!url || !url.trim()) return false;
    try {
      const u = new URL(url.trim());
      const host = (u.hostname || '').toLowerCase();
      return host.includes('youtube.com') || host.includes('youtu.be');
    } catch { return false; }
  }
  function isSpotifyUrl(url: string): boolean {
    if (!url || !url.trim()) return false;
    try {
      const u = new URL(url.trim());
      const host = (u.hostname || '').toLowerCase();
      return host.includes('open.spotify.com') || host === 'spotify.com';
    } catch { return false; }
  }

  /** Extract YouTube video ID from watch or short URL. */
  function youtubeVideoId(url: string): string | null {
    try {
      const u = new URL(url);
      if (!/youtube\.com|youtu\.be/.test(u.hostname)) return null;
      return u.searchParams.get('v') || u.pathname.split('/').filter(Boolean).pop() || null;
    } catch (_) {}
    return null;
  }

  const audioSongUrl = $derived(
    user?.profile_song_upload_url || (user?.profile_song_url && !isYouTubeUrl(user.profile_song_url) && !isSpotifyUrl(user.profile_song_url) ? user.profile_song_url : null)
  );

  type Card = { id: string; name?: string; number?: string; set_name?: string; rarity?: string; image_path?: string; artwork?: string };

  const featuredCards = $derived((user?.featured_card_ids || []).map((id) => cards.find((c) => c.id === id)).filter(Boolean) as Card[]);

  /** Use accent if it's a valid hex, else theme primary */
  const accentVar = $derived(
    user?.profile_accent_color && /^#[0-9A-Fa-f]{3,6}$/.test(user.profile_accent_color)
      ? user.profile_accent_color
      : 'var(--color-primary)'
  );

  const youtubeVideoIdResolved = $derived(
    user?.profile_song_url && isYouTubeUrl(user.profile_song_url) ? youtubeVideoId(user.profile_song_url) : null
  );

  /** Static embed URL using youtube-nocookie.com (no API script = no MIME error; no ads/tracking until play = fewer blocked requests). */
  function youtubeEmbedSrc(muted: boolean): string | null {
    const v = youtubeVideoIdResolved;
    if (!v) return null;
    const m = muted ? '1' : '0';
    return `https://www.youtube-nocookie.com/embed/${v}?autoplay=1&mute=${m}&playsinline=1`;
  }

  let user: PublicUser | null = $state(null);
  /** Start unmuted; set to false and reload embed if we need to fall back to muted autoplay. */
  let youtubeUnmuted = $state(true);
  let cards: Card[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let copied = $state(false);
  let copyTimeout: ReturnType<typeof setTimeout> | null = null;

  const userId = $derived($page.params.userId);

  async function copyProfileUrl() {
    if (!userId || typeof window === 'undefined') return;
    const url = `${window.location.origin}/u/${encodeURIComponent(userId)}`;
    try {
      await navigator.clipboard.writeText(url);
      copied = true;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => { copied = false; copyTimeout = null; }, 2000);
    } catch (_) {}
  }

  onMount(() => {
    if (!userId) {
      error = 'Invalid profile';
      loading = false;
      return;
    }
    load();
  });

  async function load() {
    if (!userId) return;
    loading = true;
    error = '';
    try {
      const profileRes = await fetchApi(`/api/public/users/${encodeURIComponent(userId)}`, { auth: false });
      if (!profileRes.ok) {
        if (profileRes.status === 404) {
          error = 'Profile not found';
          user = null;
        } else {
          throw new Error('Failed to load');
        }
        return;
      }
      user = await profileRes.json();
      const collRes = await fetchApi(`/api/public/users/${encodeURIComponent(userId)}/collection`, { auth: false });
      if (collRes.ok) {
        const data = await collRes.json();
        cards = data.cards || [];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      user = null;
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>{user?.username ?? user?.poser_username ?? 'Profile'} · Brutality Cards</title>
</svelte:head>

<div
  class="public-profile public-profile__scroll h-[100dvh] h-screen p-4 sm:p-6 font-[family:var(--font-heading)]"
  style="--profile-accent: {accentVar};"
>
  <div class="max-w-2xl mx-auto">
    {#if loading}
      <p class="text-muted-foreground text-sm">Loading…</p>
    {:else if error}
      <p class="text-destructive text-sm">{error}</p>
    {:else if user}
      <!-- MySpace/SpaceHey-style profile card -->
      <article class="profile-card rounded-2xl border-2 border-border overflow-hidden bg-card/80 shadow-xl relative">
        <!-- Accent banner strip -->
        <div class="profile-banner h-2 sm:h-3" style="background: var(--profile-accent);" aria-hidden="true"></div>

        <div class="p-5 sm:p-6 space-y-6 relative">
          <button
            type="button"
            class="absolute top-4 right-4 p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-card transition-colors"
            onclick={copyProfileUrl}
            aria-label={copied ? 'Copied!' : 'Share profile (copy link)'}
            title={copied ? 'Copied!' : 'Copy profile link'}
          >
            {#if copied}
              <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
            {:else}
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
            {/if}
          </button>
          <!-- Avatar + headline + display name -->
          <header class="text-center">
            {#if user.avatar_url}
              <img
                src={user.avatar_url}
                alt=""
                class="mx-auto w-20 h-20 sm:w-24 sm:h-24 rounded-full border-2 border-[var(--profile-accent)] object-cover shrink-0 mb-3"
              />
            {/if}
            <h1 class="profile-headline font-display text-2xl sm:text-3xl md:text-4xl tracking-tight uppercase text-foreground leading-tight">
              {user.profile_headline || user.username || user.poser_username || 'Collector'}
            </h1>
            {#if user.profile_headline && (user.username || user.poser_username)}
              <p class="text-sm text-muted-foreground mt-1">@{user.username || user.poser_username}</p>
            {:else if user.poser_username && user.username !== user.poser_username}
              <p class="text-sm text-muted-foreground mt-1 font-mono">{user.poser_username}</p>
            {/if}
          </header>

          <!-- About me -->
          {#if user.profile_bio}
            <section class="profile-section">
              <h2 class="profile-section__title">About me</h2>
              <div class="profile-bio text-sm text-foreground/90 whitespace-pre-wrap break-words">{user.profile_bio}</div>
            </section>
          {/if}

          <!-- Profile song: static iframe with youtube-nocookie.com (no external script = no MIME error; no ads until play = fewer blocked requests). -->
          {#if user.profile_song_url && isYouTubeUrl(user.profile_song_url)}
            {@const embedSrc = youtubeEmbedSrc(!youtubeUnmuted)}
            {#if embedSrc}
              <section class="profile-section">
                <h2 class="profile-section__title">Currently listening</h2>
                <div class="aspect-video rounded-lg overflow-hidden border border-border bg-black relative">
                  <iframe
                    title="Profile song"
                    src={embedSrc}
                    class="w-full h-full"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowfullscreen
                  />
                  {#if !youtubeUnmuted}
                    <button
                      type="button"
                      class="absolute bottom-2 right-2 rounded-md bg-black/70 px-3 py-1.5 text-xs font-medium text-white hover:bg-black/90 focus:outline-none focus:ring-2 focus:ring-white/50"
                      onclick={() => (youtubeUnmuted = true)}
                    >
                      Unmute
                    </button>
                  {/if}
                </div>
              </section>
            {/if}
          {:else if user.profile_song_url && isSpotifyUrl(user.profile_song_url)}
            <section class="profile-section">
              <h2 class="profile-section__title">Currently listening</h2>
              <a
                href={user.profile_song_url}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-2 rounded-lg border-2 border-[var(--profile-accent)] bg-transparent px-4 py-2.5 text-sm font-medium text-[var(--profile-accent)] hover:bg-[var(--profile-accent)]/10 transition-colors"
              >
                <span aria-hidden="true">♫</span>
                Listen on Spotify
              </a>
            </section>
          {:else if audioSongUrl}
            <section class="profile-section">
              <h2 class="profile-section__title">Currently listening</h2>
              <div class="rounded-lg border border-border bg-muted/30 p-3">
                <audio
                  controls
                  class="w-full h-10"
                  src={audioSongUrl}
                  preload="metadata"
                >
                  <a href={audioSongUrl} target="_blank" rel="noopener noreferrer" class="text-[var(--profile-accent)] hover:underline">Play profile song</a>
                </audio>
              </div>
            </section>
          {/if}

          <!-- Featured cards -->
          {#if featuredCards.length > 0}
            <section class="profile-section">
              <h2 class="profile-section__title">Featured cards</h2>
              <div class="grid grid-cols-3 gap-3">
                {#each featuredCards as card (card.id)}
                  <div class="flex flex-col items-center rounded-xl border-2 border-border bg-background/50 overflow-hidden hover:border-[var(--profile-accent)]/50 transition-colors">
                    {#if cardImageUrl(card)}
                      <img src={cardImageUrl(card)} alt={card.name ?? 'Card'} class="w-full aspect-[0.718] object-cover" />
                    {:else}
                      <div class="w-full aspect-[0.718] bg-muted flex items-center justify-center text-xs">?</div>
                    {/if}
                  </div>
                {/each}
              </div>
            </section>
          {/if}

          {#if user.collection_count > 0}
            <section class="profile-section">
              <a
                href="/catalogue?user={encodeURIComponent(user.user_id)}"
                class="block w-full text-center rounded-lg border-2 border-[var(--profile-accent)] bg-transparent px-4 py-2.5 text-sm font-medium text-[var(--profile-accent)] hover:bg-[var(--profile-accent)]/10 transition-colors"
              >
                Explore my deck
              </a>
            </section>
          {/if}
        </div>

        <div class="profile-footer text-center py-3 text-xs text-muted-foreground border-t border-border/60">
          Brutality Cards · Public profile
        </div>
      </article>
    {/if}
  </div>
</div>

<style>
  .public-profile {
    font-family: var(--font-heading);
    background: linear-gradient(180deg, hsl(var(--color-background)) 0%, hsl(var(--color-muted) / 0.3) 100%);
  }
  .public-profile__scroll {
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: hsl(var(--border)) transparent;
  }
  .public-profile__scroll::-webkit-scrollbar {
    width: 8px;
  }
  .public-profile__scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .public-profile__scroll::-webkit-scrollbar-thumb {
    background: hsl(var(--border));
    border-radius: 4px;
  }
  .public-profile__scroll::-webkit-scrollbar-thumb:hover {
    background: hsl(var(--muted-foreground) / 0.3);
  }
  .profile-card {
    background: linear-gradient(145deg, hsl(var(--color-card) / 0.95) 0%, hsl(var(--color-card)) 100%);
  }
  .profile-banner {
    background: var(--profile-accent);
  }
  .profile-section__title {
    font-family: var(--font-display);
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--profile-accent);
    margin-bottom: 0.5rem;
  }
</style>
