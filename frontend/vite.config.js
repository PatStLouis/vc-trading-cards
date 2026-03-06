import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const pwaIconSrc = (env.VITE_APP_ICON_URL || '').trim() || '/favicon.png';
  const pwaIconType = pwaIconSrc.toLowerCase().endsWith('.svg') ? 'image/svg+xml' : 'image/png';

  return {
  plugins: [
    tailwindcss(),
    sveltekit(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: null,
      devOptions: { enabled: true },
      manifest: {
        name: 'Tritone Cards',
        short_name: 'Tritone Cards',
        description: "Exclusive band collectible cards — collect your favorite members and rarities as holographic cards",
        theme_color: '#0a0a0a',
        background_color: '#0a0a0a',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        id: '/',
        categories: ['entertainment', 'games'],
        orientation: 'any',
        icons: [
          { src: pwaIconSrc, sizes: 'any', type: pwaIconType, purpose: 'any' },
          { src: pwaIconSrc, sizes: '192x192', type: pwaIconType, purpose: 'any' },
          { src: pwaIconSrc, sizes: '512x512', type: pwaIconType, purpose: 'any' },
          { src: pwaIconSrc, sizes: '512x512', type: pwaIconType, purpose: 'maskable' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/',
        navigateFallbackDenylist: [/^\/api/, /^\/auth/, /^\/uploads/]
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
