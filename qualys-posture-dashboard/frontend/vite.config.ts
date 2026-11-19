import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Single-process deploy: the built app is served by FastAPI as static files, so the base is '/'.
// In dev, proxy /api to the backend on :8770 so there's no CORS friction.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8770' },
  },
})
