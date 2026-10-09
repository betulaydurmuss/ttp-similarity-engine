import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    assetsInlineLimit: 0
  },
  test: {
    include: ['src/**/*.test.js'],
    environment: 'node'
  }
});
