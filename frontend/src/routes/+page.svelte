<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { loginWithPasskey, isWebAuthnAvailable } from '$lib/webauthn';
  import QRCodeStyling from 'qr-code-styling';
  import AppIcon from '$lib/components/AppIcon.svelte';
  import { APP_ICON_URL } from '$lib/app-icon';

  const API_BASE = import.meta.env.VITE_API_URL ?? '';

  let error = $state('');
  let passkeyError = $state('');
  let passkeyLoading = $state(false);
  let discordLoading = $state(false);
  let isDesktop = $state(false);
  let appUrl = $state('');
  let qrContainer: HTMLDivElement | null = $state(null);
  let qrCreated = false;

  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    error = params.get('error') || '';
    const ua = navigator.userAgent;
    const mobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
    isDesktop = !mobile;
    appUrl = typeof window !== 'undefined' ? window.location.origin : '';
  });

  $effect(() => {
    if (!qrContainer || !appUrl || qrCreated) return;
    qrCreated = true;
    qrContainer.innerHTML = '';
    const iconUrl = APP_ICON_URL.startsWith('http')
      ? APP_ICON_URL
      : `${appUrl}${APP_ICON_URL.startsWith('/') ? APP_ICON_URL : '/' + APP_ICON_URL}`;
    const qr = new QRCodeStyling({
      width: 96,
      height: 96,
      data: appUrl,
      image: iconUrl,
      imageOptions: { hideBackgroundDots: true, imageSize: 0.35, margin: 2, crossOrigin: 'anonymous' },
      dotsOptions: { type: 'dots', color: '#7f1d1d' },
      cornersSquareOptions: { type: 'dot', color: '#7f1d1d' },
      cornersDotOptions: { type: 'dot', color: '#7f1d1d' },
      backgroundOptions: { color: 'transparent' },
    });
    qr.append(qrContainer);
  });

  /** Build Android intent URL so Discord app opens with OAuth URL when possible; fallback to same URL in browser. */
  function buildDiscordIntentUrl(authorizeUrl: string): string {
    const fallbackEncoded = encodeURIComponent(authorizeUrl);
    const intent =
      authorizeUrl.replace(/^https:\/\//, 'intent://') +
      '#Intent;scheme=https;package=com.discord;S.browser_fallback_url=' +
      fallbackEncoded +
      ';end';
    return intent;
  }

  async function login() {
    discordLoading = true;
    try {
      const res = await fetch(`${API_BASE}/auth/discord/url`);
      if (!res.ok) {
        window.location.href = `${API_BASE}/auth/discord`;
        return;
      }
      const data = await res.json();
      const url: string = data?.url;
      if (!url) {
        window.location.href = `${API_BASE}/auth/discord`;
        return;
      }
      const isAndroid = /Android/i.test(navigator.userAgent);
      if (isAndroid) {
        window.location.href = buildDiscordIntentUrl(url);
      } else {
        window.location.href = url;
      }
    } catch {
      window.location.href = `${API_BASE}/auth/discord`;
    } finally {
      discordLoading = false;
    }
  }

  async function loginPasskey() {
    if (!isWebAuthnAvailable()) {
      passkeyError = 'failed';
      return;
    }
    passkeyError = '';
    passkeyLoading = true;
    try {
      const data = await loginWithPasskey();
      if (data.redirect) {
        window.location.href = data.redirect;
      }
    } catch {
      passkeyError = 'failed';
    } finally {
      passkeyLoading = false;
    }
  }
</script>

<main class="landing min-h-screen flex flex-col items-center justify-center text-center px-6 py-16 relative overflow-hidden">
  <!-- Background -->
  <div class="landing__bg" aria-hidden="true"></div>
  <div class="landing__grid" aria-hidden="true"></div>

  <div class="landing__content relative z-10 w-full max-w-xl">
    <!-- Logo + Badge -->
    <div class="flex items-center justify-center gap-3 mb-6">
      <AppIcon size="lg" class="rounded-xl" />
      <p class="landing__badge text-xs font-medium tracking-wider uppercase text-primary/90 mb-0">
        The Devil's Interval · Exclusive band collectibles
      </p>
    </div>

    <h1 class="landing__title font-display text-5xl sm:text-6xl md:text-7xl tracking-tight mb-4 uppercase">
      <span class="landing__title-line">Tritone</span>
      <span class="landing__title-line landing__title-accent">Cards</span>
    </h1>
    <p class="landing__tagline text-muted-foreground text-lg sm:text-xl leading-relaxed mb-10 max-w-md mx-auto">
      Exclusive holographic cards for the fandom. Collect your favorite band members, chase rarities, and show off your deck.
    </p>

    <Card.Root class="landing__card w-full border border-border/80 bg-card/95 text-card-foreground rounded-2xl shadow-2xl shadow-black/30 p-8 backdrop-blur-sm">
      <Card.Content class="space-y-5 p-0">
        {#if error}
          <p class="text-destructive text-sm font-medium">Login failed. Please try again.</p>
        {/if}
        <Button
          class="landing__cta w-full font-semibold text-base py-6 rounded-xl transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-primary/20 flex items-center justify-center gap-2"
          size="lg"
          onclick={login}
          disabled={discordLoading}
        >
          <span class="landing__discord-icon shrink-0 flex items-center justify-center" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5" aria-hidden="true">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
            </svg>
          </span>
          {discordLoading ? 'Opening Discord…' : 'Log in with Discord'}
        </Button>
        {#if isWebAuthnAvailable()}
          <Button
            variant="outline"
            class="w-full"
            size="lg"
            onclick={loginPasskey}
            disabled={passkeyLoading}
          >
            {passkeyLoading ? 'Signing in…' : 'Sign in with passkey'}
          </Button>
        {/if}
        {#if passkeyError}
          <span class="inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium bg-destructive/10 text-destructive/90 border border-destructive/20" role="status">Failed</span>
        {/if}
        <p class="text-xs text-muted-foreground font-mono">
          Your collection, your deck — one account, all your cards
        </p>
      </Card.Content>
    </Card.Root>

    <a
      href="/search"
      class="landing__browse-card mt-8 w-full block border border-border/80 bg-card/90 text-card-foreground rounded-2xl shadow-xl shadow-black/20 p-6 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer no-underline"
    >
      <div class="flex flex-col sm:flex-row sm:items-center gap-4 text-left">
        <div class="landing__browse-icon shrink-0 w-12 h-12 rounded-xl bg-primary/15 flex items-center justify-center" aria-hidden="true">
          <svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>
        <div class="min-w-0">
          <p class="font-semibold text-foreground text-lg">Browse sets &amp; find collectors</p>
          <p class="text-sm text-muted-foreground mt-0.5">Explore the catalog, see who has which cards, and discover other fans</p>
        </div>
        <span class="sm:ml-auto shrink-0 text-primary font-medium text-sm flex items-center gap-1" aria-hidden="true">
          Explore
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        </span>
      </div>
    </a>

    {#if isDesktop && appUrl}
      <Card.Root class="landing__get-app mt-8 w-full border border-border bg-card/95 text-card-foreground rounded-xl shadow-lg shadow-black/20 p-3 flex flex-row items-center gap-4 landing__get-app-card">
        <div class="landing__qr-wrap shrink-0 rounded-lg" bind:this={qrContainer} role="img" aria-label="QR code to open Tritone Cards"></div>
        <div class="text-left min-w-0">
          <p class="text-sm font-semibold text-foreground">Get app on your phone</p>
          <p class="text-xs text-muted-foreground mt-0.5">Scan to open in your browser</p>
        </div>
      </Card.Root>
    {/if}

    <ul class="landing__features mt-12 flex flex-wrap justify-center gap-6 text-sm text-muted-foreground" role="list">
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Collect
      </li>
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Exclusive
      </li>
      <li class="flex items-center gap-2">
        <span class="landing__dot" aria-hidden="true"></span>
        Fandom
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
      radial-gradient(ellipse 80% 50% at 50% -20%, oklch(0.35 0.15 25 / 0.5), transparent 55%),
      radial-gradient(ellipse 60% 40% at 100% 50%, oklch(0.2 0.08 25 / 0.35), transparent),
      radial-gradient(ellipse 60% 40% at 0% 80%, oklch(0.18 0.06 15 / 0.4), transparent);
    pointer-events: none;
  }

  .landing__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(oklch(0.2 0.03 25 / 0.5) 1px, transparent 1px),
      linear-gradient(90deg, oklch(0.2 0.03 25 / 0.5) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 70%);
    pointer-events: none;
  }

  .landing__title {
    font-family: var(--font-display);
    line-height: 0.95;
    letter-spacing: 0.04em;
  }

  .landing__title-line {
    display: block;
  }

  .landing__title-accent {
    background: linear-gradient(135deg, oklch(0.65 0.22 25), oklch(0.5 0.2 15));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  .landing__badge {
    font-family: var(--font-mono);
    letter-spacing: 0.15em;
    color: oklch(0.6 0.2 25);
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

  .landing__browse-card,
  .landing__browse-card:hover {
    text-decoration: none;
  }

  .landing__browse-card:hover {
    border-color: oklch(0.4 0.15 25);
    box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.15), 0 0 30px -10px oklch(0.55 0.22 25 / 0.2);
    transform: scale(1.01);
  }

  .landing__get-app-card {
    border-color: var(--color-border);
    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.2), 0 0 0 1px var(--color-border);
  }

  .landing__get-app-card:hover {
    border-color: oklch(0.4 0.15 25);
    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.25), 0 0 20px -5px oklch(0.55 0.22 25 / 0.3);
  }

  .landing__qr-wrap {
    width: 96px;
    height: 96px;
    flex-shrink: 0;
    overflow: hidden;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
  }

  .landing__qr-wrap canvas {
    display: block;
    width: 100% !important;
    height: 100% !important;
    border-radius: var(--radius-xl);
  }
</style>
