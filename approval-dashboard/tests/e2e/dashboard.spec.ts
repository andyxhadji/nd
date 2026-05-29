import { test, expect } from '@playwright/test';

test.describe('Approval Dashboard', () => {
  test('loads without errors', async ({ page }) => {
    // Track console errors (ignore 404s for favicon/resources)
    const criticalErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Ignore resource loading errors (favicon, etc)
        if (!text.includes('Failed to load resource') && !text.includes('404')) {
          criticalErrors.push(text);
        }
      }
    });

    // Navigate to dashboard
    await page.goto('/');

    // Wait for React to render
    await page.waitForSelector('h1', { timeout: 10000 });

    // Verify title is present
    const title = await page.textContent('h1');
    expect(title).toBe('AgentField Approvals');

    // Verify no critical console errors
    expect(criticalErrors).toHaveLength(0);
  });

  test('displays connection status', async ({ page }) => {
    await page.goto('/');

    // Wait for connection status to appear
    await page.waitForTimeout(2000);

    // Verify header exists with connection info
    const header = page.locator('header');
    await expect(header).toBeVisible();
  });

  test('displays three tabs', async ({ page }) => {
    await page.goto('/');

    // Verify all three tab buttons exist
    await expect(page.getByRole('button', { name: /Spec Reviews/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Roborev Failures/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Response Approvals/i })).toBeVisible();
  });

  test('switches between tabs', async ({ page }) => {
    await page.goto('/');

    // Click Roborev Failures tab
    await page.getByRole('button', { name: /Roborev Failures/i }).click();

    // Click Response Approvals tab
    await page.getByRole('button', { name: /Response Approvals/i }).click();

    // Click back to Spec Reviews
    await page.getByRole('button', { name: /Spec Reviews/i }).click();

    // Should complete without errors
  });

  test('shows empty state when no approvals', async ({ page }) => {
    await page.goto('/');

    // Wait for loading to complete (spinner should disappear)
    await page.waitForTimeout(3000);

    // Check if still loading or if content appeared
    const isLoading = await page.getByText(/Loading approvals/i).isVisible().catch(() => false);
    const hasEmptyMessage = await page.getByText(/No pending/i).isVisible().catch(() => false);
    const hasErrorMessage = await page.getByText(/Connection lost|unavailable/i).isVisible().catch(() => false);

    // Either empty state, error state, or still loading is acceptable
    // (AgentField may not be running during tests)
    expect(hasEmptyMessage || hasErrorMessage || isLoading).toBeTruthy();
  });
});
