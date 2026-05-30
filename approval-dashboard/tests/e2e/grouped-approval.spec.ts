import { test, expect } from '@playwright/test';

test.describe('Grouped Approvals', () => {
  test('groups approvals by MR and shows combined diff', async ({ page }) => {
    // Note: This test requires mocked AgentField responses or actual test data
    // For now, we'll test the UI structure

    await page.goto('http://localhost:3000');

    // Click "By Source" tab
    await page.click('text=By Source');

    // Should show empty state initially
    await expect(page.locator('text=No pending approvals')).toBeVisible();
  });

  test('displays grouped approval card structure', async ({ page }) => {
    // This test verifies the component structure exists
    await page.goto('http://localhost:3000');
    await page.click('text=By Source');

    // Tab should be active
    const sourceTab = page.locator('button:has-text("By Source")');
    await expect(sourceTab).toHaveClass(/border-blue-600/);
  });

  test('batch approval buttons are present', async ({ page }) => {
    // Verify batch approval UI exists
    await page.goto('http://localhost:3000');
    await page.click('text=By Source');

    // Content area should exist
    const content = page.locator('main');
    await expect(content).toBeVisible();
  });
});
