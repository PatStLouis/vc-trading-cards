<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import * as Table from '$lib/components/ui/table';

  let user: { username: string; is_admin: boolean } | null = $state(null);
  let stats: { total_users: number } | null = $state(null);
  let users: Array<{ discord_sub: string; discord_username: string; wallet_id: string; created_at: string | null }> = $state([]);
  let loading = $state(true);
  let error = $state('');

  const API = typeof window !== 'undefined' ? '' : (import.meta.env.VITE_API_URL || '');

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
      const [statsRes, usersRes] = await Promise.all([
        fetch(`${API}/api/admin/stats`, { credentials: 'include' }),
        fetch(`${API}/api/admin/users`, { credentials: 'include' })
      ]);
      if (!statsRes.ok || !usersRes.ok) throw new Error('Failed to load admin data');
      stats = await statsRes.json();
      const usersData = await usersRes.json();
      users = usersData.users || [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  });

  async function logout() {
    await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
    goto('/');
  }
</script>

<main class="admin-page py-6 px-4">
  <Card.Root class="border border-border bg-card text-card-foreground rounded-xl mb-6">
    <Card.Header class="flex flex-row flex-wrap items-center justify-between gap-4 pb-4 border-b border-border">
      <div>
        <Card.Title class="text-xl font-semibold">Admin dashboard</Card.Title>
        <Card.Description class="text-muted-foreground text-sm mt-1">
          {#if user}
            Logged in as @{user.username}
          {/if}
        </Card.Description>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" href="/wallet">Wallet</Button>
        <Button variant="outline" size="sm" onclick={logout}>Log out</Button>
      </div>
    </Card.Header>
  </Card.Root>

  {#if loading}
    <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-8">
      <Card.Content>
        <p class="text-muted-foreground">Loading…</p>
      </Card.Content>
    </Card.Root>
  {:else if error}
    <Card.Root class="border border-destructive/50 bg-card text-card-foreground rounded-xl p-6">
      <Card.Content>
        <p class="text-destructive">{error}</p>
      </Card.Content>
    </Card.Root>
  {:else}
    <div class="space-y-6">
      <Card.Root class="border border-border bg-card text-card-foreground rounded-xl p-6">
        <Card.Header>
          <Card.Title class="text-lg font-medium">Stats</Card.Title>
          <Card.Description class="text-muted-foreground text-sm">Registered users</Card.Description>
        </Card.Header>
        <Card.Content>
          <p class="text-3xl font-bold">{stats?.total_users ?? 0}</p>
        </Card.Content>
      </Card.Root>

      <Card.Root class="border border-border bg-card text-card-foreground rounded-xl overflow-hidden">
        <Card.Header class="pb-4">
          <Card.Title class="text-lg font-medium">Users</Card.Title>
          <Card.Description class="text-muted-foreground text-sm">Discord users with wallets</Card.Description>
        </Card.Header>
        <Card.Content class="p-0">
          <Table.Root>
            <Table.Header>
              <Table.Row>
                <Table.Head>Username</Table.Head>
                <Table.Head>Discord ID</Table.Head>
                <Table.Head>Wallet ID</Table.Head>
                <Table.Head class="text-right">Created</Table.Head>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {#each users as u}
                <Table.Row>
                  <Table.Cell class="font-medium">{u.discord_username || '—'}</Table.Cell>
                  <Table.Cell class="font-mono text-sm">{u.discord_sub}</Table.Cell>
                  <Table.Cell class="font-mono text-sm max-w-[200px] truncate" title={u.wallet_id}>{u.wallet_id}</Table.Cell>
                  <Table.Cell class="text-right text-muted-foreground text-sm">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </Table.Cell>
                </Table.Row>
              {/each}
            </Table.Body>
          </Table.Root>
          {#if users.length === 0}
            <p class="p-6 text-center text-muted-foreground text-sm">No users yet.</p>
          {/if}
        </Card.Content>
      </Card.Root>
    </div>
  {/if}
</main>
