import { defineConfig } from 'astro/config';

// Static output — SEO-friendly, deployable to Vercel/Netlify free tier.
export default defineConfig({
  site: 'https://bioinformatics-paper-digest.vercel.app',
  output: 'static',
});
