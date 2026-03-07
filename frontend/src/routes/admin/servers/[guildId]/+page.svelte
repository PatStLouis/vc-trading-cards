<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import * as Table from '$lib/components/ui/table';
  import { Button } from '$lib/components/ui/button';
  import { fetchAdmin, apiUrl } from '$lib/api';

  type Guild = {
    id: string;
    name: string;
    icon: string | null;
    approximate_member_count?: number;
    approximate_presence_count?: number;
  };

  type DiscordUser = {
    id: string;
    username: string;
    global_name: string | null;
    avatar: string | null;
  };

  type Member = {
    user?: DiscordUser;
    nick: string | null;
    joined_at: string | null;
    roles: string[];
    is_registered?: boolean;
  };

  const guildId = $derived(page.params.guildId);
  const API = apiUrl();

  let guild: Guild | null = $state(null);
  let members: Member[] = $state([]);
  let loading = $state(true);
  let membersLoading = $state(false);
  let error = $state('');
  let membersError = $state('');
  let after: string | null = $state(null);
  let search = $state('');

  function guildIconUrl(g: Guild | null): string | null {
    if (!g?.icon) return null;
    return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
  }

  function userAvatarUrl(m: Member): string | null {
    const u = m.user;
    if (!u?.avatar) return null;
    return `https://cdn.discordapp.com/avatars/${u.id}/${u.avatar}.png`;
  }

  function displayName(m: Member): string {
    if (m.nick?.trim()) return m.nick;
    if (m.user?.global_name?.trim()) return m.user.global_name;
    return m.user?.username ?? '—';
  }

  async function loadGuild() {
    if (!guildId) return;
    try {
      const res = await fetchAdmin(`/api/admin/discord/guilds/${guildId}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || res.statusText || 'Failed to load server');
      }
      guild = await res.json();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    }
  }

  async function loadMembers(append = false) {
    if (!guildId) return;
    membersLoading = true;
    membersError = '';
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (append && after) params.set('after', after);
      const res = await fetchAdmin(`/api/admin/discord/guilds/${guildId}/members?${params}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || res.statusText || 'Failed to load members');
      }
      const data = await res.json();
      const list = data.members || [];
      if (append) {
        members = [...members, ...list];
      } else {
        members = list;
      }
      if (list.length === 100 && list[list.length - 1]?.user?.id) {
        after = list[list.length - 1].user.id;
      } else {
        after = null;
      }
    } catch (e) {
      membersError = e instanceof Error ? e.message : 'Failed to load members';
    } finally {
      membersLoading = false;
    }
  }

  onMount(async () => {
    loading = true;
    await loadGuild();
    loading = false;
    if (!error && guildId) await loadMembers();
  });

  const filteredMembers = $derived(
    !search.trim()
      ? members
      : members.filter((m) => {
          const name = displayName(m).toLowerCase();
          const username = (m.user?.username ?? '').toLowerCase();
          const id = m.user?.id ?? '';
          const q = search.toLowerCase().trim();
          return name.includes(q) || username.includes(q) || id.includes(q);
        })
  );
</script>

<svelte:head>
  <title>{guild?.name ?? 'Server'} · Admin</title>
</svelte:head>

<div class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <div class="flex items-center gap-3 min-w-0">
      <a href="/admin/servers" class="text-neutral-400 hover:text-white shrink-0">← Servers</a>
      {#if guild}
        {#if guildIconUrl(guild)}
          <img
            src={guildIconUrl(guild)!}
            alt=""
            class="h-10 w-10 rounded-full object-cover bg-neutral-700 shrink-0"
          />
        {:else}
          <div class="h-10 w-10 rounded-full bg-neutral-700 flex items-center justify-center text-neutral-500 text-sm font-medium shrink-0">
            {(guild.name || '?').charAt(0).toUpperCase()}
          </div>
        {/if}
        <div class="min-w-0">
          <h1 class="text-lg font-semibold text-neutral-100 truncate">{guild.name}</h1>
          <p class="text-sm text-neutral-400">
            {guild.approximate_member_count != null ? guild.approximate_member_count.toLocaleString() : '—'} members
            {#if guild.approximate_presence_count != null}
              · {guild.approximate_presence_count.toLocaleString()} online
            {/if}
          </p>
        </div>
      {/if}
    </div>
  </div>

  {#if loading && !guild}
    <div class="py-12 text-center text-neutral-500 text-sm">Loading server…</div>
  {:else if error}
    <div class="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-400 text-sm">{error}</div>
  {:else if guild}
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h2 class="text-sm font-medium text-neutral-300">Members</h2>
      <input
        type="search"
        placeholder="Search by name or ID…"
        bind:value={search}
        class="w-full sm:w-64 rounded-lg border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:border-neutral-500" />
    </div>

    {#if membersError}
      <div class="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-400 text-sm">
        {membersError}
        <p class="mt-1 text-xs text-neutral-500">Ensure the bot has the Server Members Intent enabled in the Discord Developer Portal (Bot → Privileged Gateway Intents).</p>
      </div>
    {:else}
      <div class="rounded-xl border border-neutral-700 bg-neutral-800/80 overflow-hidden">
        <div class="overflow-x-auto">
          <Table.Root>
            <Table.Header>
              <Table.Row class="border-b border-neutral-700 hover:bg-transparent">
                <Table.Head class="h-10 w-12 px-2 py-3"></Table.Head>
                <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">User</Table.Head>
                <Table.Head class="h-10 w-20 px-4 py-3 text-center text-xs font-medium text-neutral-400 uppercase tracking-wider">Registered</Table.Head>
                <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">User ID</Table.Head>
                <Table.Head class="h-10 px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">Joined</Table.Head>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {#each filteredMembers as m}
                <Table.Row class="border-b border-neutral-700/80 last:border-0 hover:bg-neutral-700/40 transition-colors">
                  <Table.Cell class="w-12 px-2 py-3">
                    {#if userAvatarUrl(m)}
                      <img
                        src={userAvatarUrl(m)!}
                        alt=""
                        class="h-8 w-8 rounded-full object-cover bg-neutral-700"
                      />
                    {:else}
                      <div class="h-8 w-8 rounded-full bg-neutral-700 flex items-center justify-center text-neutral-500 text-xs font-medium">
                        {displayName(m).charAt(0).toUpperCase() || '?'}
                      </div>
                    {/if}
                  </Table.Cell>
                  <Table.Cell class="px-4 py-3 font-medium text-neutral-100">
                    {displayName(m)}
                    {#if m.nick && m.user?.username && m.nick !== m.user.username}
                      <span class="text-neutral-500 text-xs ml-1">@{m.user.username}</span>
                    {/if}
                  </Table.Cell>
                  <Table.Cell class="px-4 py-3 text-center">
                    {#if m.is_registered}
                      <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400" title="Registered on app">
                        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                      </span>
                    {:else}
                      <span class="text-neutral-600">—</span>
                    {/if}
                  </Table.Cell>
                  <Table.Cell class="px-4 py-3 font-mono text-sm text-neutral-400">{m.user?.id ?? '—'}</Table.Cell>
                  <Table.Cell class="px-4 py-3 text-sm text-neutral-400 whitespace-nowrap">
                    {m.joined_at ? new Date(m.joined_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—'}
                  </Table.Cell>
                </Table.Row>
              {/each}
            </Table.Body>
          </Table.Root>
        </div>
        {#if filteredMembers.length === 0}
          <div class="py-12 text-center text-neutral-500 text-sm">
            {search.trim() ? 'No members match your search.' : 'No members loaded. Enable Server Members Intent in the Discord Developer Portal.'}
          </div>
        {:else if after && !membersLoading}
          <div class="p-4 border-t border-neutral-700 flex justify-center">
            <Button
              variant="outline"
              size="sm"
              class="border-neutral-600 text-neutral-200 hover:bg-neutral-700"
              onclick={() => loadMembers(true)}
              disabled={membersLoading}>
              Load more
            </Button>
          </div>
        {:else if membersLoading}
          <div class="p-4 border-t border-neutral-700 text-center text-neutral-500 text-sm">Loading…</div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
