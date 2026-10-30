import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        headers: process.env.VITE_AUTH_MODE === 'local' ? {
          'X-Gilberto-Proxy-Auth': process.env.GILBERTO_PROXY_SECRET || 'unconfigured',
        } : {},
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
