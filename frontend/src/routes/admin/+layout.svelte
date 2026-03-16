<script lang="ts">
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { fade } from 'svelte/transition';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import AppIcon from '$lib/components/AppIcon.svelte';
  import { fetchApi } from '$lib/api';

  let { children } = $props();
  let user: { username: string; is_admin: boolean; avatar_url?: string | null } | null = $state(null);
  let ready = $state(false);
  let mobileNavOpen = $state(false);

  const API = import.meta.env.VITE_API_URL ?? '';

  const nav = [
    { href: '/admin', label: 'Overview' },
    { href: '/admin/users', label: 'Users' },
    { href: '/admin/manage-cards', label: 'Cards' },
    { href: '/admin/ledger', label: 'Ledger' },
    { href: '/admin/servers', label: 'Servers' },
    { href: '/admin/agent', label: 'Agent' },
  ];

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
        goto('/wallet?admin_required=1');
        return;
      }
    } catch {
      goto('/');
    } finally {
      ready = true;
    }
  });

  async function logout() {
    await fetchApi('/auth/logout', { method: 'POST', auth: true });
    goto('/');
  }
</script>

<style>
  .admin-theme.admin-layout {
    background: #171717; /* neutral-900 */
  }
  .admin-theme .admin-sidebar {
    background: #0a0a0a; /* neutral-950 */
    border-right: 1px solid #404040; /* neutral-700 */
  }
  .admin-theme .admin-main main {
    max-width: none;
    background: #1c1c1c; /* neutral-900-ish, slightly lighter than sidebar */
  }
  @supports (padding-bottom: env(safe-area-inset-bottom)) {
    .admin-main main {
      padding-bottom: calc(1.5rem + env(safe-area-inset-bottom));
    }
  }
</style>

{#if !ready}
  <div class="flex min-h-screen items-center justify-center text-muted-foreground text-xs">Loading…</div>
{:else if !user}
  <!-- redirecting -->
{:else}
  <div class="admin-layout flex min-h-screen text-sm admin-theme">
    <aside class="admin-sidebar hidden w-56 shrink-0 sm:flex flex-col py-4">
      <div class="px-4 pb-4 flex items-center gap-2">
        {#if user.avatar_url}
          <img src={user.avatar_url} alt="" class="w-10 h-10 rounded-lg object-cover shrink-0 border border-neutral-700" width="40" height="40" />
        {:else}
          <span class="w-10 h-10 rounded-lg flex items-center justify-center bg-neutral-700 text-neutral-200 text-sm font-semibold shrink-0 border border-neutral-600" aria-hidden="true">{(user.username || '?').charAt(0).toUpperCase()}</span>
        {/if}
        <div class="min-w-0">
          <a href="/wallet" class="font-semibold text-white hover:text-neutral-200 transition-colors">Brutality Cards</a>
          <span class="text-neutral-400 text-xs block mt-0.5 truncate">@{user.username}</span>
        </div>
      </div>
      <nav class="flex flex-col gap-0.5 px-3 pt-2">
        {#each nav as item}
          <a
            href={item.href}
            class="rounded-lg px-3 py-2 text-sm font-medium transition-colors {($page.url.pathname === item.href || (item.href !== '/admin' && $page.url.pathname.startsWith(item.href)))
              ? 'bg-neutral-700 text-white'
              : 'text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200'}">
            {item.label}
          </a>
        {/each}
      </nav>
      <div class="mt-auto flex flex-col gap-0.5 border-t border-neutral-700 pt-4 px-3">
        <a href="/wallet" class="rounded-lg px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200">My deck</a>
        <button
          type="button"
          class="rounded-lg px-3 py-2 text-left text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
          onclick={logout}>
          Log out
        </button>
      </div>
    </aside>

    <div class="flex-1 flex flex-col min-w-0 admin-main">
      <header class="sm:hidden sticky top-0 z-10 flex h-14 items-center justify-between border-b border-neutral-800 bg-neutral-900 px-4 safe-area-inset-top">
        <button
          type="button"
          class="flex h-10 w-10 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-800 hover:text-white transition-colors -ml-1"
          aria-label="Open menu"
          onclick={() => (mobileNavOpen = true)}
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <a href="/admin" class="font-semibold text-white flex items-center gap-2 absolute left-1/2 -translate-x-1/2">
          <AppIcon size="sm" class="rounded" />
          <span>Admin</span>
        </a>
        <div class="w-10" aria-hidden="true"></div>
      </header>

      <!-- Mobile nav drawer -->
      {#if mobileNavOpen}
        <div
          class="sm:hidden fixed inset-0 z-20"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <button
            type="button"
            class="absolute inset-0 bg-black/60"
            aria-label="Close menu"
            onclick={() => (mobileNavOpen = false)}
            transition:fade={{ duration: 150 }}
          ></button>
          <div
            class="admin-drawer absolute left-0 top-0 bottom-0 w-72 max-w-[85vw] flex flex-col bg-neutral-950 border-r border-neutral-700 shadow-xl"
            transition:fly={{ x: -280, duration: 200 }}
          >
            <div class="flex h-14 items-center justify-between border-b border-neutral-700 px-4 shrink-0">
              <span class="font-semibold text-white">Menu</span>
              <button
                type="button"
                class="flex h-10 w-10 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-800 hover:text-white transition-colors"
                aria-label="Close menu"
                onclick={() => (mobileNavOpen = false)}
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div class="flex-1 overflow-y-auto py-4">
              <div class="px-4 pb-4 flex items-center gap-3">
                {#if user.avatar_url}
                  <img src={user.avatar_url} alt="" class="w-10 h-10 rounded-lg object-cover shrink-0 border border-neutral-700" width="40" height="40" />
                {:else}
                  <span class="w-10 h-10 rounded-lg flex items-center justify-center bg-neutral-700 text-neutral-200 text-sm font-semibold shrink-0 border border-neutral-600" aria-hidden="true">{(user.username || '?').charAt(0).toUpperCase()}</span>
                {/if}
                <div class="min-w-0">
                  <a href="/wallet" class="font-semibold text-white hover:text-neutral-200 transition-colors block truncate" onclick={() => (mobileNavOpen = false)}>Brutality Cards</a>
                  <span class="text-neutral-400 text-xs block mt-0.5 truncate">@{user.username}</span>
                </div>
              </div>
              <nav class="flex flex-col gap-0.5 px-3">
                {#each nav as item}
                  <a
                    href={item.href}
                    class="flex items-center min-h-[44px] rounded-lg px-3 py-3 text-sm font-medium transition-colors {($page.url.pathname === item.href || (item.href !== '/admin' && $page.url.pathname.startsWith(item.href)))
                      ? 'bg-neutral-700 text-white'
                      : 'text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200'}"
                    onclick={() => (mobileNavOpen = false)}>
                    {item.label}
                  </a>
                {/each}
              </nav>
              <div class="mt-4 pt-4 border-t border-neutral-700 flex flex-col gap-0.5 px-3">
                <a href="/wallet" class="flex items-center min-h-[44px] rounded-lg px-3 py-3 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200" onclick={() => (mobileNavOpen = false)}>My deck</a>
                <button
                  type="button"
                  class="flex items-center min-h-[44px] rounded-lg px-3 py-3 text-left text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 w-full"
                  onclick={() => { mobileNavOpen = false; logout(); }}>
                  Log out
                </button>
              </div>
            </div>
          </div>
        </div>
      {/if}

      <main class="flex-1 w-full max-w-none px-4 py-5 sm:px-6 sm:py-6 lg:px-10 lg:py-8 overflow-x-hidden">
        {@render children()}
      </main>
    </div>
  </div>
{/if}
