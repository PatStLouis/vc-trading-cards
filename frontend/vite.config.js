import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const pwaIconSrc = (env.VITE_APP_ICON_URL || '').trim() || '/favicon.png';
  const pwaIconType = pwaIconSrc.toLowerCase().endsWith('.svg') ? 'image/svg+xml' : 'image/png';
  const isDefaultFavicon = !(env.VITE_APP_ICON_URL || '').trim();
  const pwaIcons = isDefaultFavicon
    ? []
    : [
        { src: pwaIconSrc, sizes: 'any', type: pwaIconType, purpose: 'any' },
        { src: pwaIconSrc, sizes: '192x192', type: pwaIconType, purpose: 'any' },
        { src: pwaIconSrc, sizes: '512x512', type: pwaIconType, purpose: 'any' },
        { src: pwaIconSrc, sizes: '512x512', type: pwaIconType, purpose: 'maskable' }
      ];

  return {
  plugins: [
    tailwindcss(),
    sveltekit(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: null,
      devOptions: { enabled: true },
      manifest: {
        name: 'Brutality Cards',
        short_name: 'Brutality Cards',
        description: "Exclusive band collectible cards — collect your favorite members and rarities as holographic cards",
        theme_color: '#0a0a0a',
        background_color: '#0a0a0a',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        id: '/',
        categories: ['entertainment', 'games'],
        orientation: 'any',
        icons: pwaIcons
      },
      workbox: {
        // In dev, dev-dist only has sw.js and workbox-*.js (ignored), so glob would match nothing and warn
        globPatterns: mode === 'development' ? [] : ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Don't precache the document so deploy updates always get fresh HTML (correct chunk hashes)
        globIgnores: [
          '**/index.html',
          'index.html',
          // Large static assets exceed Workbox default 2 MiB; load from network when needed
          '**/twitch-base.png',
          '**/logos/brutality-logo2.png'
        ],
        // Disable navigate fallback: plugin defaults to navigateFallback: 'index.html', which uses createHandlerBoundToURL and throws non-precached-url since we don't precache index.html.
        navigateFallback: null,
        navigateFallbackDenylist: [/^\/api/, /^\/auth/, /^\/uploads/],
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true
      }
    })
  ],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
  },
  server: {
    port: 5175,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/uploads': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
  };
});
