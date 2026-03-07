<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import AppIcon from '$lib/components/AppIcon.svelte';
  import { fetchApi } from '$lib/api';

  type PublicUser = {
    user_id: string;
    username: string | null;
    poser_username: string | null;
    collection_count: number;
  };

  let loading = $state(true);
  let error = $state('');
  let me: { user_id?: string } | null = $state(null);
  let profile: PublicUser | null = $state(null);

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
      const userId = me?.user_id;
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
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
      profile = null;
    } finally {
      loading = false;
    }
  }

  onMount(() => load());
</script>

<svelte:head>
  <title>Profile · Tritone Cards</title>
</svelte:head>

<div class="profile-page py-5 px-4 relative">
  <div class="profile-page__bg absolute inset-0 -z-10 bg-background/95" aria-hidden="true"></div>

  <div class="relative z-10 max-w-xl mx-auto space-y-4">
    <header class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2 min-w-0">
        <a href="/wallet" class="shrink-0 rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors" aria-label="Back to deck">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
        </a>
        <AppIcon size="sm" class="rounded-md shrink-0 hidden sm:block" />
        <h1 class="font-display text-xl sm:text-2xl tracking-tight uppercase truncate">Profile</h1>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <Button variant="ghost" size="sm" href="/wallet/account">Account</Button>
        <Button variant="ghost" size="sm" href="/wallet">My deck</Button>
      </div>
    </header>

    {#if loading}
      <div class="rounded-xl border border-border/80 bg-card/50 py-8 text-center text-sm text-muted-foreground">Loading…</div>
    {:else if error}
      <div class="rounded-xl border border-destructive/50 bg-card/50 p-4">
        <p class="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" class="mt-2" onclick={load}>Retry</Button>
      </div>
    {:else if profile}
      <p class="text-xs text-muted-foreground">This is what others see when they look up your profile.</p>

      <section class="rounded-xl border border-border/80 bg-card/50 overflow-hidden">
        <div class="p-4 space-y-4">
          <div>
            <p class="text-[10px] uppercase tracking-wide text-muted-foreground">Display name</p>
            <p class="text-sm font-medium mt-0.5">{profile.username || '—'}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wide text-muted-foreground">Poser username</p>
            <p class="text-sm font-mono mt-0.5">{profile.poser_username || '—'}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wide text-muted-foreground">Collection</p>
            <p class="text-sm font-medium mt-0.5">
              {profile.collection_count} {profile.collection_count === 1 ? 'card' : 'cards'}
            </p>
          </div>
          <div class="flex flex-wrap gap-2 pt-2">
            <Button variant="outline" size="sm" href="/wallet">View my deck</Button>
            <Button variant="outline" size="sm" href="/wallet/account">Edit account</Button>
          </div>
        </div>
      </section>
    {/if}
  </div>
</div>

<style>
  .profile-page__bg {
    min-height: 100vh;
  }
</style>
