import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: './static',
    emptyOutDir: true,
  },
  server: {
    host: '0.0.0.0',  // Allow external connections
    port: 5173,
    proxy: {
      '/v1': {
        target: 'http://localhost:8088',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8088',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8088',
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {
            // Suppress WebSocket proxy errors (connection resets are normal)
          });
        },
      },
    },
  },
})

