<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import { fetchApi } from '$lib/api';

  type Props = {
    title: string;
    user: { username: string; avatar_url?: string | null; is_admin?: boolean } | null;
    /** When true show "Explore catalogue" link; when false show "My deck" link */
    showExploreButton?: boolean;
    /** When true show "Home" link to main screen and, when not logged in, "Log in" button */
    showHomeLink?: boolean;
  };

  let { title, user, showExploreButton = true, showHomeLink = false }: Props = $props();

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
      {/if}
    </nav>
    <div class="flex items-center gap-4 shrink-0">
      {#if user}
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
