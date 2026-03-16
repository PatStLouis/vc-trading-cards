import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      fallback: 'index.html',
      prerender: { entries: [] }
    }),
    // Force absolute asset URLs (/_app/...) so scripts load correctly when the page is served at a path like /wallet/profile
    paths: {
      base: '',
      assets: '/'
    },
    csrf: { trustedOrigins: ['http://localhost:5173', 'http://127.0.0.1:5173'] }
  }
};

export default config;
