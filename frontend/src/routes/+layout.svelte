<script lang="ts">
  import { onMount } from 'svelte';
  import { APP_ICON_URL } from '$lib/app-icon';
  import '../app.css';
  import '$lib/styles/cards.css';

  onMount(() => {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      import('virtual:pwa-register').then(({ registerSW }) => {
        registerSW({ immediate: true });
      });
    }
  });
</script>

<svelte:head>
  <title>Tritone Cards — Exclusive band collectible cards</title>
  <link rel="icon" href={APP_ICON_URL} />
</svelte:head>

<slot />
