import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests-local',
  use: { baseURL: 'http://127.0.0.1:5174', headless: true },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: !process.env.CI,
    env: { VITE_AUTH_MODE: 'local',
           GILBERTO_PROXY_SECRET: 'playwright-only-local-backend-secret' },
  },
})
