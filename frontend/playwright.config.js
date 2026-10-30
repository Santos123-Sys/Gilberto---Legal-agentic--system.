import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  // In CI, also emit failures as GitHub annotations (visible on the PR).
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: { baseURL: 'http://127.0.0.1:5173', headless: true },
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI, env: {
    VITE_OIDC_AUTHORIZATION_ENDPOINT: 'https://id.example.test/authorize',
    VITE_OIDC_TOKEN_ENDPOINT: 'https://id.example.test/token',
    VITE_OIDC_CLIENT_ID: 'gilberto-playwright-public-client',
    VITE_OIDC_API_AUDIENCE: 'gilberto-test-api',
  } },
})
