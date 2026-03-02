<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';

  let error = $state('');

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    error = params.get('error') || '';
  });

  function login() {
    window.location.href = '/auth/discord';
  }
</script>

<main class="min-h-screen flex flex-col items-center justify-center text-center px-6 py-12">
  <Card.Root class="w-full max-w-lg border border-border bg-card text-card-foreground rounded-xl shadow-lg p-8">
    <Card.Header class="space-y-2 text-center pb-4">
      <Card.Title class="text-2xl font-bold tracking-tight">VC Trading Cards</Card.Title>
      <Card.Description class="text-muted-foreground text-sm leading-relaxed">
        Your verifiable credential trading cards in one place. Log in with Discord to browse your wallet.
      </Card.Description>
    </Card.Header>
    <Card.Content class="space-y-4">
      {#if error}
        <p class="text-destructive text-sm">Login failed. Please try again.</p>
      {/if}
      <Button
        class="w-full"
        size="lg"
        onclick={login}
      >
        Log in with Discord
      </Button>
    </Card.Content>
    <Card.Footer class="pt-4 border-t border-border text-center">
      <p class="text-xs text-muted-foreground">Uses ACA-Py multitenancy. Each user gets their own wallet.</p>
    </Card.Footer>
  </Card.Root>
</main>
