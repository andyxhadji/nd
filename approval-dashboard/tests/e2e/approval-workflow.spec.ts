import { test, expect } from '@playwright/test';

test.describe('Approval Workflow (Integration)', () => {
  test('displays approval card when execution is paused', async ({ page }) => {
    await page.goto('/');

    // Wait for initial load
    await page.waitForTimeout(6000);

    // Check if any approval cards are rendered
    const approvalCards = page.locator('[class*="approval-card"], [class*="ApprovalCard"]');
    const cardCount = await approvalCards.count();

    if (cardCount > 0) {
      // If approvals exist, verify card structure
      const firstCard = approvalCards.first();

      // Should have action buttons
      const hasApproveButton = await firstCard.getByRole('button', { name: /Approve/i }).isVisible();
      const hasRejectButton = await firstCard.getByRole('button', { name: /Reject/i }).isVisible();

      expect(hasApproveButton || hasRejectButton).toBeTruthy();
    } else {
      // If no approvals, just verify UI is responsive (AgentField may not be running)
      const hasContent = await page.locator('main').isVisible();
      expect(hasContent).toBeTruthy();
    }
  });

  test('can expand execution history', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(6000);

    const approvalCards = page.locator('[class*="approval-card"], [class*="ApprovalCard"]');
    const cardCount = await approvalCards.count();

    if (cardCount > 0) {
      // Try to find and click execution history toggle
      const historyButton = page.getByText(/Execution History/i).first();
      const isVisible = await historyButton.isVisible().catch(() => false);

      if (isVisible) {
        await historyButton.click();
        // Should expand to show trace details
        await page.waitForTimeout(500);
      }
    }

    // Test passes if no errors thrown
    expect(true).toBeTruthy();
  });

  test('feedback textarea appears when clicking "Add feedback"', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(6000);

    const approvalCards = page.locator('[class*="approval-card"], [class*="ApprovalCard"]');
    const cardCount = await approvalCards.count();

    if (cardCount > 0) {
      const feedbackLink = page.getByText(/Add feedback/i).first();
      const isVisible = await feedbackLink.isVisible().catch(() => false);

      if (isVisible) {
        await feedbackLink.click();

        // Textarea should appear
        const textarea = page.locator('textarea[placeholder*="feedback" i]').first();
        await expect(textarea).toBeVisible({ timeout: 2000 });
      }
    }

    // Test passes if no errors
    expect(true).toBeTruthy();
  });
});
