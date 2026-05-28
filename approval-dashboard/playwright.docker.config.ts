import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for testing the Docker Compose deployment.
 *
 * Usage:
 *   docker compose up -d
 *   npm run test:docker
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // No webServer - Docker Compose handles it
  // Assumes dashboard service is already running on port 3000
});
