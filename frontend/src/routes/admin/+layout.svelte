<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
  import AppIcon from '$lib/components/AppIcon.svelte';

  let user: { username: string; is_admin: boolean } | null = $state(null);
  let ready = $state(false);

  const API = import.meta.env.VITE_API_URL ?? '';

  const nav = [
    { href: '/admin', label: 'Overview' },
    { href: '/admin/users', label: 'Users' },
    { href: '/admin/manage-cards', label: 'Cards' },
    { href: '/admin/agent', label: 'Agent' },
  ];

  onMount(async () => {
    try {
      const meRes = await fetch(`${API}/api/me`, { credentials: 'include' });
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
    } catch {
      goto('/');
    } finally {
      ready = true;
    }
  });

  async function logout() {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
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
</style>

{#if !ready}
  <div class="flex min-h-screen items-center justify-center text-muted-foreground text-xs">Loading…</div>
{:else if !user}
  <!-- redirecting -->
{:else}
  <div class="admin-layout flex min-h-screen text-sm admin-theme">
    <aside class="admin-sidebar hidden w-56 shrink-0 sm:flex flex-col py-4">
      <div class="px-4 pb-4 flex items-center gap-2">
        <AppIcon size="md" class="rounded-lg" />
        <div>
          <a href="/wallet" class="font-semibold text-white hover:text-neutral-200 transition-colors">Tritone Cards</a>
          <span class="text-neutral-400 text-xs block mt-0.5">Admin</span>
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
      <header class="sm:hidden sticky top-0 z-10 flex h-12 items-center justify-between border-b border-neutral-800 bg-neutral-900 px-4">
        <a href="/admin" class="font-semibold text-white flex items-center gap-2">
          <AppIcon size="sm" class="rounded" />
          <span>Admin</span>
        </a>
        <div class="flex gap-2">
          <a href="/admin/users" class="cursor-pointer rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 transition-colors">Users</a>
          <a href="/admin/manage-cards" class="cursor-pointer rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 transition-colors">Cards</a>
          <a href="/admin/agent" class="cursor-pointer rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 transition-colors">Agent</a>
          <a href="/wallet" class="cursor-pointer rounded-lg px-3 py-1.5 text-sm text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 transition-colors">My deck</a>
        </div>
      </header>
      <main class="flex-1 w-full max-w-none px-4 py-5 sm:px-6 sm:py-6 lg:px-10 lg:py-8">
        <slot />
      </main>
    </div>
  </div>
{/if}
