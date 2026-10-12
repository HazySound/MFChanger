import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [svelte()],
  server: { port: 5173, strictPort: true },   // main.py --dev 가 이 주소를 연다
  build: { target: 'es2022', chunkSizeWarningLimit: 800 },
})
