<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';

  const API_BASE = import.meta.env.VITE_API_URL ?? '';

  let error = $state('');

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    error = params.get('error') || '';
  });

  function login() {
    window.location.href = `${API_BASE}/auth/discord`;
  }
</script>

<main class="landing min-h-screen flex flex-col items-center justify-center text-center px-6 py-16 relative overflow-hidden">
  <!-- Background -->
  <div class="landing__bg" aria-hidden="true"></div>
  <div class="landing__grid" aria-hidden="true"></div>

  <div class="landing__content relative z-10 w-full max-w-xl">
    <!-- Badge -->
    <p class="landing__badge text-xs font-medium tracking-wider uppercase text-primary/90 mb-6">
      The Devil's Interval · Verifiable credentials
    </p>

    <h1 class="landing__title text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight mb-4">
      <span class="landing__title-line">Tritone</span>
      <span class="landing__title-line landing__title-accent">Cards</span>
    </h1>
    <p class="landing__tagline text-muted-foreground text-lg sm:text-xl leading-relaxed mb-10 max-w-md mx-auto">
      The Devil's Interval Collectible Cards. Collect, verify, and own your credentials as holographic cards—one wallet, all your proofs.
    </p>

    <Card.Root class="landing__card w-full border border-border/80 bg-card/95 text-card-foreground rounded-2xl shadow-2xl shadow-black/30 p-8 backdrop-blur-sm">
      <Card.Content class="space-y-5 p-0">
        {#if error}
          <p class="text-destructive text-sm font-medium">Login failed. Please try again.</p>
        {/if}
        <Button
          class="landing__cta w-full font-semibold text-base py-6 rounded-xl transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-primary/20"
          size="lg"
          onclick={login}
        >
          Log in with Discord
        </Button>
        <p class="text-xs text-muted-foreground font-mono">
          ACA-Py multitenancy · Your own subwallet on first login
        </p>
      </Card.Content>
    </Card.Root>

    <ul class="landing__features mt-12 flex flex-wrap justify-center gap-6 text-sm text-muted-foreground" role="list">
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Collect
      </li>
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Verify
      </li>
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Own
      </li>
    </ul>
  </div>
</main>

<style>
  .landing {
    --landing-glow: 120px;
  }

  .landing__bg {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 80% 50% at 50% -20%, oklch(0.32 0.12 25 / 0.4), transparent),
      radial-gradient(ellipse 60% 40% at 100% 50%, oklch(0.25 0.1 280 / 0.2), transparent),
      radial-gradient(ellipse 60% 40% at 0% 80%, oklch(0.28 0.1 15 / 0.25), transparent);
    pointer-events: none;
  }

  .landing__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(oklch(0.22 0 0 / 0.4) 1px, transparent 1px),
      linear-gradient(90deg, oklch(0.22 0 0 / 0.4) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 70%);
    pointer-events: none;
  }

  .landing__title {
    font-family: var(--font-heading);
    line-height: 1.1;
  }

  .landing__title-line {
    display: block;
  }

  .landing__title-accent {
    background: linear-gradient(135deg, oklch(0.72 0.18 25), oklch(0.58 0.22 15));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .landing__badge {
    font-family: var(--font-mono);
    letter-spacing: 0.15em;
  }

  .landing__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-primary);
    opacity: 0.9;
  }

  .landing__features {
    font-family: var(--font-heading);
  }
</style>
