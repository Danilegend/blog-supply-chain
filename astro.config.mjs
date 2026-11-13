import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://Danilegend.github.io',
  base: '/blog-supply-chain',
   integrations: [sitemap()],
});