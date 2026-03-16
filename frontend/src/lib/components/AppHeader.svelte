<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import { fetchApi } from '$lib/api';

  type Props = {
    title: string;
    user: { username: string; avatar_url?: string | null; is_admin?: boolean; pending_issued_count?: number } | null;
    /** When true show "Explore catalogue" link; when false show "My deck" link */
    showExploreButton?: boolean;
    /** When true show "Home" link to main screen and, when not logged in, "Log in" button */
    showHomeLink?: boolean;
  };

  let { title, user, showExploreButton = true, showHomeLink = false }: Props = $props();

  const pendingCount = $derived(user?.pending_issued_count ?? 0);
  const hasNotifications = $derived(pendingCount > 0);

  let menuOpen = $state(false);
  let menuButtonEl: HTMLButtonElement | null = $state(null);
  let menuEl: HTMLDivElement | null = $state(null);

  onMount(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') menuOpen = false;
    }
    function onClick(e: MouseEvent) {
      const target = e.target as Node;
      if (menuOpen && menuButtonEl && !menuButtonEl.contains(target) && menuEl && !menuEl.contains(target)) menuOpen = false;
    }
    window.addEventListener('keydown', onKey);
    document.addEventListener('click', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onClick);
    };
  });

  async function logout() {
    await fetchApi('/auth/logout', { method: 'POST', auth: true });
    goto('/');
  }
</script>

<header class="app-header mb-8 md:mb-10">
  <div class="flex items-center justify-between gap-3">
    <nav class="flex items-center gap-4 sm:gap-5 min-w-0" aria-label="Main">
      <h1 class="app-header__title font-display text-2xl sm:text-3xl md:text-4xl tracking-tight uppercase truncate min-w-0">
        {title}
      </h1>
      {#if !user && showExploreButton}
        <Button variant="outline" size="sm" href="/catalogue" class="shrink-0 no-underline hover:no-underline transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98]">Explore catalogue</Button>
        <Button variant="ghost" size="sm" href="/ledger" class="shrink-0 no-underline hover:no-underline">Ledger</Button>
      {/if}
    </nav>
    <div class="flex items-center gap-4 shrink-0">
      {#if user}
        <a
          href="/wallet"
          class="app-header__bell relative flex items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background {hasNotifications ? 'h-10 w-10' : 'h-9 w-9 opacity-80'}"
          aria-label={hasNotifications ? `${pendingCount} new card(s) in your deck — go to My Deck` : 'My Deck'}
        >
          <svg class="{hasNotifications ? 'w-5 h-5' : 'w-4 h-4'}" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {#if hasNotifications}
            <span class="app-header__bell-badge absolute -top-0.5 -right-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
              {pendingCount > 99 ? '99+' : pendingCount}
            </span>
          {/if}
        </a>
        <span class="app-header__meta text-muted-foreground text-sm truncate max-w-[120px] sm:max-w-[180px]">@{user.username}</span>
        <div class="app-header__menu relative">
          <button
            type="button"
            bind:this={menuButtonEl}
            class="app-header__avatar-btn rounded-full border-2 border-border bg-card overflow-hidden focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background hover:border-primary/50 transition-colors"
            aria-label="Account menu"
            aria-expanded={menuOpen}
            aria-haspopup="true"
            onclick={() => (menuOpen = !menuOpen)}
          >
            {#if user.avatar_url}
              <img src={user.avatar_url} alt="" class="w-9 h-9 sm:w-10 sm:h-10 object-cover" width="40" height="40" />
            {:else}
              <span class="app-header__avatar-fallback w-9 h-9 sm:w-10 sm:h-10 flex items-center justify-center bg-primary/20 text-primary text-sm font-semibold">
                {(user.username || '?').charAt(0).toUpperCase()}
              </span>
            {/if}
          </button>
          {#if menuOpen}
            <div
              bind:this={menuEl}
              class="app-header__dropdown absolute right-0 top-full mt-2 py-1 min-w-[160px] rounded-lg border border-border bg-card shadow-lg z-50"
              role="menu"
            >
              <a href="/wallet" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent rounded-none first:rounded-t-lg focus:outline-none focus:bg-accent" role="menuitem">My Deck</a>
              <a href="/catalogue" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent focus:outline-none focus:bg-accent" role="menuitem">Browse Catalogue</a>
              <a href="/ledger" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent focus:outline-none focus:bg-accent" role="menuitem">Ledger</a>
              <a href="/wallet/account" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent focus:outline-none focus:bg-accent" role="menuitem">Account</a>
              <a href="/wallet/profile" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent focus:outline-none focus:bg-accent" role="menuitem">Profile</a>
              {#if user.is_admin}
                <a href="/admin" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent focus:outline-none focus:bg-accent" role="menuitem">Admin</a>
              {/if}
              <button type="button" class="app-header__dropdown-item block w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-accent last:rounded-b-lg focus:outline-none focus:bg-accent border-t border-border mt-1 pt-2" role="menuitem" onclick={() => { menuOpen = false; logout(); }}>Log out</button>
            </div>
          {/if}
        </div>
      {:else if showHomeLink}
        <Button variant="outline" size="sm" href="/" class="shrink-0 no-underline hover:no-underline">Log in</Button>
      {/if}
    </div>
  </div>
</header>

<style>
  .app-header__title {
    font-family: var(--font-display);
  }
  .app-header__dropdown-item:focus {
    background: hsl(var(--accent));
  }
</style>
