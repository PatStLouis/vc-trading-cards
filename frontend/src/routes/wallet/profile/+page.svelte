<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import AppHeader from '$lib/components/AppHeader.svelte';
  import { fetchApi, apiUrl } from '$lib/api';

  type PublicUser = {
    user_id: string;
    username: string | null;
    poser_username: string | null;
    collection_count: number;
    featured_card_ids?: string[];
    profile_headline?: string | null;
    profile_bio?: string | null;
    profile_song_url?: string | null;
    profile_song_upload_url?: string | null;
    profile_accent_color?: string | null;
  };

  type CollectionCard = {
    id: string;
    name?: string;
    number?: string;
    set_name?: string;
    rarity?: string;
    image_path?: string;
    artwork?: string;
  };

  const API = apiUrl();

  function cardImageUrl(card: CollectionCard): string {
    const u = card?.image_path ?? card?.artwork ?? '';
    if (!u) return '';
    const base = (API || '').replace(/\/$/, '');
    return u.startsWith('http') ? u : u.startsWith('/') ? `${base}${u}` : `${base}/uploads/${u}`;
  }

  let loading = $state(true);
  let error = $state('');
  type MeProfile = {
    user_id?: string;
    username?: string;
    avatar_url?: string | null;
    is_admin?: boolean;
    pending_issued_count?: number;
    featured_card_ids?: string[];
    profile_headline?: string | null;
    profile_bio?: string | null;
    profile_song_url?: string | null;
    profile_song_upload_url?: string | null;
    profile_accent_color?: string | null;
  };
  let me: MeProfile | null = $state(null);
  let profile: PublicUser | null = $state(null);
  let collection: CollectionCard[] = $state([]);
  let featuredIds: string[] = $state([]);
  let profileHeadline = $state('');
  let profileBio = $state('');
  let profileSongUrl = $state('');
  let profileSongUploadUrl = $state<string | null>(null);
  type SongSource = 'youtube' | 'direct' | 'upload' | 'spotify';
  let profileSongSource = $state<SongSource>('youtube');
  let profileAccentColor = $state('');
  let showPreview = $state(false);
  let savingFeatured = $state(false);
  let savingProfile = $state(false);
  let uploadingSong = $state(false);

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

  async function load() {
    loading = true;
    error = '';
    try {
      const meRes = await fetchApi('/api/me', { auth: true });
      if (meRes.status === 401) {
        goto('/');
        return;
      }
      if (!meRes.ok) throw new Error('Failed to load');
      me = await meRes.json();
      const m = me as MeProfile;
      featuredIds = [...(m.featured_card_ids || [])];
      profileHeadline = m.profile_headline ?? '';
      profileBio = m.profile_bio ?? '';
      profileSongUrl = m.profile_song_url ?? '';
      profileSongUploadUrl = m.profile_song_upload_url ?? null;
      if (m.profile_song_upload_url) profileSongSource = 'upload';
      else if (m.profile_song_url && isYouTubeUrl(m.profile_song_url)) profileSongSource = 'youtube';
      else if (m.profile_song_url && isSpotifyUrl(m.profile_song_url)) profileSongSource = 'spotify';
      else if (m.profile_song_url) profileSongSource = 'direct';
      else profileSongSource = 'youtube';
      profileAccentColor = m.profile_accent_color ?? '';
      const userId = m.user_id;
      if (!userId) {
        error = 'User not found';
        return;
      }
      const profileRes = await fetchApi(`/api/public/users/${encodeURIComponent(userId)}`, { auth: false });
      if (!profileRes.ok) {
        if (profileRes.status === 404) {
          profile = {
            user_id: userId,
            username: null,
            poser_username: null,
            collection_count: 0,
          };
        } else {
          throw new Error('Failed to load profile');
        }
      } else {
        profile = await profileRes.json();
      }
      const collRes = await fetchApi(`/api/public/users/${encodeURIComponent(userId)}/collection`, { auth: false });
      if (collRes.ok) {
        const data = await collRes.json();
        collection = data.cards || [];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      profile = null;
    } finally {
      loading = false;
    }
  }

  function toggleFeatured(cardId: string) {
    const i = featuredIds.indexOf(cardId);
    if (i >= 0) {
      featuredIds = featuredIds.filter((id) => id !== cardId);
    } else if (featuredIds.length < 3) {
      featuredIds = [...featuredIds, cardId];
    }
  }

  async function saveFeatured() {
    if (!me?.user_id || savingFeatured) return;
    savingFeatured = true;
    try {
      const res = await fetchApi('/api/me', {
        method: 'PATCH',
        auth: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ featured_card_ids: featuredIds }),
      });
      if (!res.ok) throw new Error('Failed to save');
      const data = await res.json();
      featuredIds = [...(data.featured_card_ids || [])];
      if (profile) profile = { ...profile, featured_card_ids: featuredIds };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      savingFeatured = false;
    }
  }

  async function uploadProfileSong(file: File) {
    if (!me?.user_id || uploadingSong) return;
    uploadingSong = true;
    error = '';
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetchApi('/api/me/profile-song-upload', { auth: true, method: 'POST', body: form });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(typeof errBody?.detail === 'string' ? errBody.detail : 'Upload failed');
      }
      const data = await res.json();
      profileSongUploadUrl = data.profile_song_upload_url ?? null;
      profileSongSource = 'upload';
      profileSongUrl = '';
      if (me) me = { ...me, profile_song_url: null, profile_song_upload_url: data.profile_song_upload_url };
      if (profile) profile = { ...profile, profile_song_url: null };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploadingSong = false;
    }
  }

  async function removeProfileSong() {
    if (!me?.user_id || uploadingSong) return;
    uploadingSong = true;
    error = '';
    try {
      const res = await fetchApi('/api/me/profile-song', { auth: true, method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to remove');
      const data = await res.json();
      profileSongUploadUrl = data.profile_song_upload_url ?? null;
      profileSongUrl = '';
      if (data.profile_song_upload_url) profileSongSource = 'upload';
      else profileSongSource = 'youtube';
      if (me) me = { ...me, profile_song_url: data.profile_song_url, profile_song_upload_url: data.profile_song_upload_url };
      if (profile) profile = { ...profile, profile_song_url: data.profile_song_url };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to remove';
    } finally {
      uploadingSong = false;
    }
  }

  async function saveProfileCustomization() {
    if (!me?.user_id || savingProfile) return;
    savingProfile = true;
    error = '';
    try {
      const body: Record<string, unknown> = {
        profile_headline: profileHeadline.trim() || null,
        profile_bio: profileBio.trim() || null,
        profile_accent_color: profileAccentColor.trim() || null,
      };
      if (profileSongSource === 'youtube' || profileSongSource === 'direct' || profileSongSource === 'spotify') {
        body.profile_song_url = profileSongUrl.trim() || null;
      }
      const res = await fetchApi('/api/me', {
        method: 'PATCH',
        auth: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(typeof errBody?.detail === 'string' ? errBody.detail : 'Failed to save');
      }
      const data = await res.json();
      profileHeadline = data.profile_headline ?? '';
      profileBio = data.profile_bio ?? '';
      profileSongUrl = data.profile_song_url ?? '';
      profileSongUploadUrl = data.profile_song_upload_url ?? null;
      if (data.profile_song_upload_url) profileSongSource = 'upload';
      else if (data.profile_song_url && isYouTubeUrl(data.profile_song_url)) profileSongSource = 'youtube';
      else if (data.profile_song_url && isSpotifyUrl(data.profile_song_url)) profileSongSource = 'spotify';
      else if (data.profile_song_url) profileSongSource = 'direct';
      else profileSongSource = 'youtube';
      profileAccentColor = data.profile_accent_color ?? '';
      if (me) me = { ...me, profile_headline: data.profile_headline, profile_bio: data.profile_bio, profile_song_url: data.profile_song_url, profile_song_upload_url: data.profile_song_upload_url, profile_accent_color: data.profile_accent_color };
      if (profile) profile = { ...profile, profile_headline: data.profile_headline, profile_bio: data.profile_bio, profile_song_url: data.profile_song_url, profile_accent_color: data.profile_accent_color };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to save';
    } finally {
      savingProfile = false;
    }
  }

  onMount(() => load());
</script>

<svelte:head>
  <title>Profile · Brutality Cards</title>
</svelte:head>

<div class="app-page py-8 px-4 md:py-10 relative">
  <div class="app-page__bg" aria-hidden="true"></div>
  <div class="texture-overlay" aria-hidden="true"></div>

  <div class="relative z-10 max-w-2xl mx-auto space-y-4">
    <AppHeader title="Profile" user={me ? { username: me.username ?? '', avatar_url: me.avatar_url, is_admin: me.is_admin, pending_issued_count: me.pending_issued_count } : null} showExploreButton={false} />

    {#if loading}
      <div class="rounded-xl border border-border/80 bg-card/50 py-8 text-center text-sm text-muted-foreground">Loading…</div>
    {:else if error}
      <div class="rounded-xl border border-destructive/50 bg-card/50 p-4">
        <p class="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" class="mt-2" onclick={load}>Retry</Button>
      </div>
    {:else if profile}
      <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
        <p class="text-xs text-muted-foreground">This is what others see when they look up your profile.</p>
        <Button variant="destructive" size="sm" class="font-bold ml-auto" onclick={() => (showPreview = true)}>Preview public profile</Button>
      </div>

      <section class="rounded-xl border border-border/80 bg-card/50 overflow-hidden">
        <div class="p-4 space-y-4">
          <div class="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs">
            <span class="text-muted-foreground">Display name</span>
            <span class="font-medium text-foreground">{profile.username || '—'}</span>
            <span class="text-muted-foreground" aria-hidden="true">·</span>
            <span class="text-muted-foreground">Poser</span>
            <span class="font-mono text-foreground">{profile.poser_username || '—'}</span>
            <span class="text-muted-foreground" aria-hidden="true">·</span>
            <span class="text-muted-foreground">Collection</span>
            <span class="font-medium text-foreground">{profile.collection_count} {profile.collection_count === 1 ? 'card' : 'cards'}</span>
          </div>

          <!-- MySpace/SpaceHey-style profile customizations -->
          <div class="border-t border-border/60 pt-4">
            <p class="text-[10px] uppercase tracking-wide text-muted-foreground mb-3">Customize your profile</p>
            <p class="text-xs text-muted-foreground mb-3">Headline, bio, and profile song appear on your public profile. Make it yours.</p>
            <div class="space-y-3">
              <div>
                <label for="profile-headline" class="text-xs text-muted-foreground">Headline</label>
                <input
                  id="profile-headline"
                  type="text"
                  bind:value={profileHeadline}
                  maxlength="200"
                  placeholder="e.g. Collector · Metalhead · Card enthusiast"
                  class="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label for="profile-bio" class="text-xs text-muted-foreground">About me</label>
                <textarea
                  id="profile-bio"
                  bind:value={profileBio}
                  maxlength="5000"
                  rows="4"
                  placeholder="Tell the world a bit about yourself..."
                  class="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                />
              </div>
              <div>
                <p class="text-xs text-muted-foreground mb-2">Profile song</p>
                <div class="flex flex-wrap gap-3 mb-2">
                  <label class="flex items-center gap-1.5 cursor-pointer">
                    <input type="radio" name="song-source" value="youtube" bind:group={profileSongSource} />
                    <span class="text-sm">YouTube</span>
                  </label>
                  <label class="flex items-center gap-1.5 cursor-pointer">
                    <input type="radio" name="song-source" value="direct" bind:group={profileSongSource} />
                    <span class="text-sm">Direct link</span>
                  </label>
                  <label class="flex items-center gap-1.5 cursor-pointer">
                    <input type="radio" name="song-source" value="upload" bind:group={profileSongSource} />
                    <span class="text-sm">Upload file</span>
                  </label>
                  <label class="flex items-center gap-1.5 cursor-pointer">
                    <input type="radio" name="song-source" value="spotify" bind:group={profileSongSource} />
                    <span class="text-sm">Spotify</span>
                  </label>
                </div>
                {#if profileSongSource === 'youtube'}
                  <input
                    id="profile-song"
                    type="url"
                    bind:value={profileSongUrl}
                    placeholder="https://youtube.com/watch?v=... or youtu.be/..."
                    class="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p class="mt-1 text-[10px] text-muted-foreground">YouTube link. Music category only when validated.</p>
                {:else if profileSongSource === 'direct'}
                  <input
                    id="profile-song-direct"
                    type="url"
                    bind:value={profileSongUrl}
                    placeholder="https://example.com/track.mp3"
                    class="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p class="mt-1 text-[10px] text-muted-foreground">Direct URL to an audio file (MP3, OGG, etc.).</p>
                {:else if profileSongSource === 'spotify'}
                  <input
                    id="profile-song-spotify"
                    type="url"
                    bind:value={profileSongUrl}
                    placeholder="https://open.spotify.com/track/... or user/playlist/album"
                    class="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p class="mt-1 text-[10px] text-muted-foreground">Spotify track, playlist, album or profile link.</p>
                {:else}
                  <div class="mt-1 space-y-2">
                    {#if profileSongUploadUrl}
                      <p class="text-sm text-muted-foreground">Uploaded. <button type="button" class="text-primary hover:underline" onclick={removeProfileSong}>Remove</button></p>
                    {:else}
                      <input
                        id="profile-song-file"
                        type="file"
                        accept="audio/mpeg,audio/mp3,audio/ogg,audio/webm,audio/mp4"
                        class="text-sm"
                        onchange={(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) uploadProfileSong(f); (e.target as HTMLInputElement).value = ''; }}
                      />
                      <p class="text-[10px] text-muted-foreground">MP3, OGG, WebM or M4A. Max 5MB.</p>
                    {/if}
                  </div>
                {/if}
              </div>
              <div>
                <label for="profile-accent" class="text-xs text-muted-foreground">Profile accent color</label>
                <div class="mt-1 flex gap-2 items-center">
                  <input
                    id="profile-accent"
                    type="text"
                    bind:value={profileAccentColor}
                    maxlength="20"
                    placeholder="#c41e3a or leave blank"
                    class="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {#if profileAccentColor}
                    {@const hex = profileAccentColor.startsWith('#') && /^#[0-9A-Fa-f]{3,6}$/.test(profileAccentColor)}
                    <span
                      class="w-8 h-8 rounded-full border border-border shrink-0"
                      style="background-color: {hex ? profileAccentColor : 'var(--color-muted)'}"
                      aria-hidden="true"
                    />
                  {/if}
                </div>
              </div>
              <Button variant="outline" size="sm" onclick={saveProfileCustomization} disabled={savingProfile || uploadingSong}>
                {savingProfile ? 'Saving…' : uploadingSong ? 'Uploading…' : 'Save profile'}
              </Button>
            </div>
          </div>

          <!-- Featured cards: select up to 3 to display on public profile -->
          <div>
            <p class="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">Cards on your profile</p>
            <p class="text-xs text-muted-foreground mb-3">Choose up to 3 cards to show on your public profile. These are visible to everyone.</p>
            {#if collection.length === 0}
              <p class="text-xs text-muted-foreground">Sync your deck first — you need at least one card to feature.</p>
            {:else}
              <div class="flex flex-nowrap gap-2 mb-3 overflow-x-auto">
                {#each featuredIds as id}
                  {@const card = collection.find((c) => c.id === id)}
                  <div class="flex items-center gap-2 rounded-lg border border-border bg-background/80 p-2 shrink-0">
                    {#if card}
                      {#if cardImageUrl(card)}
                        <img src={cardImageUrl(card)} alt="" class="h-10 w-auto rounded object-cover" />
                      {:else}
                        <span class="h-10 w-10 rounded bg-muted flex items-center justify-center text-xs">?</span>
                      {/if}
                    <span class="text-xs font-medium max-w-[100px] truncate">{card?.name ?? id}</span>
                    <button
                      type="button"
                      class="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      aria-label="Remove from profile"
                      onclick={() => toggleFeatured(id)}
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  {/if}
                  </div>
                {/each}
              </div>
              {#if featuredIds.length < 3}
                <p class="text-xs text-muted-foreground mb-2">Click a card below to add it to your profile ({featuredIds.length}/3).</p>
                <div class="card-picker-scroll grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-48 overflow-y-auto">
                  {#each collection.filter((c) => !featuredIds.includes(c.id)) as card (card.id)}
                    <button
                      type="button"
                      class="flex flex-col items-center rounded-lg border border-border bg-background/50 p-2 hover:border-primary/50 hover:bg-accent/30 transition-colors text-left"
                      onclick={() => toggleFeatured(card.id)}
                    >
                      {#if cardImageUrl(card)}
                        <img src={cardImageUrl(card)} alt="" class="w-full aspect-[0.718] rounded object-cover mb-1" />
                      {:else}
                        <div class="w-full aspect-[0.718] rounded bg-muted flex items-center justify-center text-xs mb-1">?</div>
                      {/if}
                      <span class="text-[10px] truncate w-full">{card.name ?? card.id}</span>
                    </button>
                  {/each}
                </div>
              {/if}
              {#if featuredIds.length > 0}
                <Button variant="outline" size="sm" class="mt-2" onclick={saveFeatured} disabled={savingFeatured}>
                  {savingFeatured ? 'Saving…' : 'Save profile cards'}
                </Button>
              {/if}
            {/if}
          </div>

        </div>
      </section>

      <!-- Secured iframe preview of public profile -->
      {#if showPreview && profile?.user_id}
        <div
          class="profile-preview-overlay fixed inset-0 z-[999999] flex flex-col bg-background/95 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Public profile preview"
        >
          <div class="flex items-center justify-between gap-2 p-3 border-b border-border bg-card/80 shrink-0">
            <h2 class="font-display text-lg tracking-tight uppercase">Public profile preview</h2>
            <button
              type="button"
              class="rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Close preview"
              onclick={() => (showPreview = false)}
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <div class="flex-1 min-h-0 p-3">
            <iframe
              title="Public profile view"
              src="/u/{encodeURIComponent(profile.user_id)}"
              class="profile-preview-iframe w-full h-full rounded-lg border border-border bg-background"
              sandbox="allow-same-origin allow-scripts"
              referrerpolicy="strict-origin-when-cross-origin"
            />
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .card-picker-scroll {
    scrollbar-width: thin;
    scrollbar-color: var(--color-primary) var(--color-muted);
  }
  .card-picker-scroll::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  .card-picker-scroll::-webkit-scrollbar-track {
    background: var(--color-muted);
    border-radius: 4px;
  }
  .card-picker-scroll::-webkit-scrollbar-thumb {
    background: var(--color-primary);
    border-radius: 4px;
  }
  .card-picker-scroll::-webkit-scrollbar-thumb:hover {
    background: var(--color-primary);
    filter: brightness(1.15);
  }
</style>
