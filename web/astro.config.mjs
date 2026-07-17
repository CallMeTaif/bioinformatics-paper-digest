import { defineConfig } from 'astro/config';

// Static output — SEO-friendly, deployable to Vercel/Netlify free tier.
export default defineConfig({
  site: 'https://example.com', // set to the real domain before deploy
  output: 'static',
});
