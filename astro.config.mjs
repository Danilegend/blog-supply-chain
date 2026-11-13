import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://danilegend.github.io',
  base: '/blog-supply-chain',
  integrations: [sitemap()],
});
