<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { loginWithPasskey, isWebAuthnAvailable } from '$lib/webauthn';
  import QRCodeStyling from 'qr-code-styling';
  import { apiUrl } from '$lib/api';

  const API_BASE = apiUrl();

  let error = $state('');
  let passkeyError = $state('');
  let passkeyLoading = $state(false);
  let discordLoading = $state(false);
  let twitchLoading = $state(false);
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
    const catalogueUrl = `${appUrl.replace(/\/$/, '')}/catalogue`;
    const qr = new QRCodeStyling({
      width: 96,
      height: 96,
      data: catalogueUrl,
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

  async function loginTwitch() {
    twitchLoading = true;
    try {
      const res = await fetch(`${API_BASE}/auth/login/url?provider=twitch`);
      if (!res.ok) {
        window.location.href = `${API_BASE}/auth/login?provider=twitch`;
        return;
      }
      const data = await res.json();
      const url: string = data?.url;
      if (!url) {
        window.location.href = `${API_BASE}/auth/login?provider=twitch`;
        return;
      }
      window.location.href = url;
    } catch {
      window.location.href = `${API_BASE}/auth/login?provider=twitch`;
    } finally {
      twitchLoading = false;
    }
  }

  async function login() {
    discordLoading = true;
    try {
      const res = await fetch(`${API_BASE}/auth/login/url?provider=discord`);
      if (!res.ok) {
        window.location.href = `${API_BASE}/auth/login?provider=discord`;
        return;
      }
      const data = await res.json();
      const url: string = data?.url;
      if (!url) {
        window.location.href = `${API_BASE}/auth/login?provider=discord`;
        return;
      }
      const isAndroid = /Android/i.test(navigator.userAgent);
      if (isAndroid) {
        window.location.href = buildDiscordIntentUrl(url);
      } else {
        window.location.href = url;
      }
    } catch {
      window.location.href = `${API_BASE}/auth/login?provider=discord`;
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

<main class="landing min-h-screen flex flex-col items-center justify-center px-6 py-16 relative overflow-hidden">
  <!-- Background: organic blobs + Twitch BASE blend + texture -->
  <div class="landing__bg" aria-hidden="true"></div>
  <div class="landing__twitch-blend" aria-hidden="true"></div>
  <div class="texture-overlay" aria-hidden="true"></div>

  <div class="landing__content relative z-10 w-full max-w-xl">
    <!-- Badge -->
    <div class="landing__hero-head flex flex-col items-center gap-4 mb-6 sm:mb-8">
      <p class="landing__badge text-xs font-medium tracking-wider uppercase text-primary/90 mb-0">
        Brutality Podcast · Exclusive collectibles
      </p>
    </div>

    <div class="landing__title-block relative">
      <img
        src="/logos/brutality-logo2.png"
        alt=""
        class="landing__title-logo"
        width="240"
        height="120"
        aria-hidden="true"
      />
      <h1 class="landing__title font-display text-5xl sm:text-6xl md:text-7xl tracking-tight mb-3 uppercase text-center">
        <span class="landing__title-line">Brutality</span>
        <span class="landing__title-line landing__title-accent">Cards</span>
      </h1>
    </div>

    <Card.Root class="landing__card mt-8 w-full border-none bg-card/95 text-card-foreground p-6 sm:p-8 backdrop-blur-sm">
      <Card.Content class="space-y-5 p-0">
        <h2 class="landing__auth-title font-display text-xl tracking-wide uppercase text-foreground text-center mb-3">Login</h2>
        {#if error}
          <p class="text-destructive text-sm font-medium">
            {#if error === 'auth_failed'}
              Login failed. Please try again.
            {:else if error === 'token_exchange_failed'}
              Could not complete login. Please try again.
            {:else if error === 'user_fetch_failed'}
              Could not load your account. Please try again.
            {:else}
              Something went wrong. Please try again.
            {/if}
          </p>
        {/if}
        <Button
          class="landing__cta w-full font-display font-semibold text-base tracking-wide py-6 rounded-xl"
          size="lg"
          onclick={login}
          disabled={discordLoading}
        >
          <span class="landing__discord-icon shrink-0 flex items-center justify-center" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5" aria-hidden="true">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
            </svg>
          </span>
          {discordLoading ? '…' : 'Discord'}
        </Button>
        <Button
          variant="outline"
          class="w-full font-display font-semibold py-5 rounded-xl"
          size="lg"
          onclick={loginTwitch}
          disabled={twitchLoading}
        >
          <span class="shrink-0 flex items-center justify-center" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5" aria-hidden="true">
              <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z"/>
            </svg>
          </span>
          {twitchLoading ? '…' : 'Twitch'}
        </Button>
        {#if isWebAuthnAvailable()}
          <Button
            variant="outline"
            class="w-full font-display py-5 rounded-xl flex items-center justify-center gap-2"
            size="lg"
            onclick={loginPasskey}
            disabled={passkeyLoading}
          >
            <span class="shrink-0 flex items-center justify-center" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </span>
            {passkeyLoading ? '…' : 'Passkey'}
          </Button>
        {/if}
        {#if passkeyError}
          <span class="inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium bg-destructive/10 text-destructive/90 border border-destructive/20" role="status">Failed</span>
        {/if}
      </Card.Content>
    </Card.Root>

    <a
      href="/catalogue"
      class="landing__browse-card mt-6 w-full block border border-border/80 bg-card/90 text-card-foreground p-4 sm:p-5 min-h-[56px] sm:min-h-0 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background cursor-pointer no-underline active:opacity-90 touch-manipulation"
      aria-label="Browse sets and collectors"
    >
      <div class="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 text-left">
        <div class="landing__browse-icon shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-primary/15 flex items-center justify-center" aria-hidden="true">
          <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="font-semibold text-foreground font-display text-base sm:text-lg tracking-wide">Browse sets &amp; collectors</p>
          <p class="text-xs sm:text-sm text-muted-foreground mt-0.5">Explore the catalog</p>
        </div>
        {#if isDesktop && appUrl}
          <div class="landing__qr-wrap shrink-0 rounded-lg" bind:this={qrContainer} role="img" aria-label="QR code to open public catalogue"></div>
        {/if}
      </div>
    </a>

    <ul class="landing__features mt-10 flex flex-wrap justify-center gap-x-8 gap-y-4 text-sm text-muted-foreground font-display tracking-wide uppercase" role="list">
      <li class="flex items-center gap-2 landing__feature-item landing__feature-item--1"><span class="landing__dot" aria-hidden="true"></span>Collect</li>
      <li class="flex items-center gap-2 landing__feature-item landing__feature-item--2"><span class="landing__dot" aria-hidden="true"></span>Exclusive</li>
      <li class="flex items-center gap-2 landing__feature-item landing__feature-item--3"><span class="landing__dot" aria-hidden="true"></span>Fandom</li>
    </ul>
  </div>
</main>

<style>
  .landing {
    --landing-glow: 120px;
  }

  /* Organic, unstructured background – irregular blobs */
  .landing__bg {
    position: fixed;
    inset: 0;
    z-index: 0;
    background:
      radial-gradient(ellipse 55% 70% at 35% 10%, oklch(0.32 0.14 25 / 0.55), transparent 50%),
      radial-gradient(ellipse 70% 45% at 85% 60%, oklch(0.22 0.09 25 / 0.4), transparent 55%),
      radial-gradient(ellipse 50% 60% at 10% 85%, oklch(0.2 0.07 15 / 0.45), transparent 50%),
      radial-gradient(ellipse 40% 50% at 70% 15%, oklch(0.25 0.1 25 / 0.3), transparent 45%),
      radial-gradient(ellipse 60% 35% at 50% 50%, oklch(0.15 0.05 25 / 0.25), transparent 60%);
    pointer-events: none;
  }

  /* Twitch BASE_V7 blended over the gradient */
  .landing__twitch-blend {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background-image: url('/twitch-base.png');
    background-size: cover;
    background-position: center;
    opacity: 0.4;
    mix-blend-mode: soft-light;
  }

  .landing__hero-head {
    transform: rotate(-0.8deg);
  }

  .landing__title-block {
    position: relative;
    margin-bottom: 0.25rem;
    min-height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    transform: rotate(0.6deg);
  }

  .landing__title-logo {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 1;
    width: 100%;
    max-width: min(560px, 95vw);
    height: auto;
    max-height: 320px;
    object-fit: contain;
    pointer-events: none;
  }

  .landing__title {
    position: relative;
    z-index: 0;
    font-family: var(--font-display);
    line-height: 0.92;
    letter-spacing: 0.05em;
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
    transform: rotate(0.5deg);
  }

  .landing__card {
    border: none;
    border-radius: 1rem;
    box-shadow: 0 24px 48px -12px rgb(0 0 0 / 0.35);
    transform: rotate(-0.5deg);
  }

  .landing__browse-card {
    border-radius: 1rem;
    box-shadow: 0 18px 36px -10px rgb(0 0 0 / 0.25), 0 0 0 1px oklch(0.25 0.04 25 / 0.4);
    transform: rotate(0.7deg);
  }

  @media (max-width: 640px) {
    .landing__browse-card {
      transform: none;
      border-radius: 0.75rem;
    }
  }

  .landing__browse-card:hover {
    transform: rotate(0.7deg) scale(1.01);
  }

  @media (max-width: 640px) {
    .landing__browse-card:hover {
      transform: scale(1.01);
    }
  }

  .landing__dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-primary);
    opacity: 0.9;
  }

  .landing__features {
    font-family: var(--font-display);
  }

  .landing__feature-item--1 { transform: rotate(-0.4deg); }
  .landing__feature-item--2 { transform: rotate(0.6deg); }
  .landing__feature-item--3 { transform: rotate(-0.3deg); }

  .landing__browse-card {
    text-decoration: none;
  }

  .landing__browse-card:hover {
    border-color: oklch(0.4 0.15 25);
    box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.2), 0 0 30px -10px oklch(0.55 0.22 25 / 0.25);
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
