import { test, expect } from '@playwright/test';

test.describe('Docker Networking', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'Network API only in Chromium');

  test('can reach AgentField API from browser', async ({ page }) => {
    await page.goto('/');

    // Intercept network requests to AgentField
    const agentfieldRequests: string[] = [];
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('localhost:8081') || url.includes('agentfield')) {
        agentfieldRequests.push(url);
      }
    });

    // Wait for initial API call
    await page.waitForTimeout(6000); // Wait for first 5s poll + buffer

    // Should have attempted to fetch runs
    const hasApiRequest = agentfieldRequests.some(url =>
      url.includes('/api/v1/runs') || url.includes('status=waiting')
    );

    expect(hasApiRequest).toBeTruthy();
  });

  test('handles AgentField connection errors gracefully', async ({ page }) => {
    // Track console errors (ignore resource loading errors)
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!text.includes('Failed to load resource') && !text.includes('404')) {
          consoleErrors.push(text);
        }
      }
    });

    await page.goto('/');

    // Wait for connection attempt
    await page.waitForTimeout(6000);

    // App should still be interactive (not crash)
    const isInteractive = await page.locator('h1').isVisible();
    expect(isInteractive).toBeTruthy();

    // Should not have unhandled exceptions in console
    const hasCriticalErrors = consoleErrors.some(err =>
      err.includes('Uncaught') || err.includes('TypeError')
    );
    expect(hasCriticalErrors).toBeFalsy();
  });
});
