import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

// Check if SSL certs exist for HTTPS dev server
const certsDir = path.resolve(__dirname, '../backend/certs')
const certFile = path.join(certsDir, 'cert.pem')
const keyFile = path.join(certsDir, 'key.pem')
const hasSSLCerts = fs.existsSync(certFile) && fs.existsSync(keyFile)

// Use HTTPS if certs are available
const httpsConfig = hasSSLCerts
  ? { key: fs.readFileSync(keyFile), cert: fs.readFileSync(certFile) }
  : undefined

// Backend URL - use HTTPS if certs available
const backendProtocol = hasSSLCerts ? 'https' : 'http'
const backendWsProtocol = hasSSLCerts ? 'wss' : 'ws'
const backendUrl = `${backendProtocol}://localhost:8088`
const backendWsUrl = `${backendWsProtocol}://localhost:8088`

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
    https: httpsConfig,
    proxy: {
      '/v1': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,  // Accept self-signed certs
      },
      '/health': {
        target: backendUrl,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendWsUrl,
        ws: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', () => {
            // Suppress WebSocket proxy errors (connection resets are normal)
          });
        },
      },
    },
  },
})

