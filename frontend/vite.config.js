import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,   // listen on 0.0.0.0 so LAN access works
    port: 5173,
    open: true,
    proxy: {
      // All /api requests are forwarded to the backend.
      // The browser sees them as same-origin (no CORS needed).
      // Works regardless of which IP the frontend is accessed from.
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
