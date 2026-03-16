<script lang="ts">
  import '../app.css';
  import '$lib/styles/cards.css';

  let { status, error }: { status: number; error: App.Error } = $props();

  const title = $derived(
    status === 404
      ? 'Page not found'
      : status >= 500
        ? 'Something went wrong'
        : 'Error'
  );

  const description = $derived(
    status === 404
      ? 'The page you’re looking for doesn’t exist or was moved.'
      : status >= 500
        ? 'We hit a server error. Please try again in a moment.'
        : error?.message || 'Something went wrong.'
  );

  const showMessage = $derived(status !== 404 && status < 500 && error?.message);
</script>

<svelte:head>
  <title>{title} · Brutality Cards</title>
</svelte:head>

<div class="error-page min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6 font-[family:var(--font-heading)]">
  <div class="max-w-md w-full text-center space-y-6">
    <p class="text-6xl sm:text-8xl font-display tracking-tight text-primary/80" aria-hidden="true">{status}</p>
    <h1 class="font-display text-2xl sm:text-3xl uppercase tracking-tight">{title}</h1>
    <p class="text-muted-foreground text-sm sm:text-base">{description}</p>
    {#if showMessage}
      <p class="text-xs text-muted-foreground/80 font-mono rounded-lg bg-muted/50 px-3 py-2 text-left break-words">
        {error.message}
      </p>
    {/if}
    <div class="flex flex-wrap gap-3 justify-center pt-2">
      <a
        href="/"
        class="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
      >
        Back to home
      </a>
      <button
        type="button"
        class="inline-flex items-center justify-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent/50 transition-colors"
        onclick={() => window.history.back()}
      >
        Go back
      </button>
    </div>
  </div>
</div>
