import { ApprovalContext, DiffTab } from '../api/types';

const MAX_COMBINED_LINES = 10000;

function extractDiffFromApproval(approval: ApprovalContext): string | null {
  // Extract diff based on approval type
  if (approval.roborev?.diff) {
    return approval.roborev.diff;
  }
  // Note: spec approvals don't have diffs (no code changes yet)
  // Response approvals would need diff fetching from execute_changes
  // For now, only roborev has diffs readily available
  return null;
}

function getReasonerName(approval: ApprovalContext): string {
  const reasonerMap: Record<string, string> = {
    spec: 'plan_changes',
    roborev: 'execute_changes',
    post: 'execute_changes',
  };
  return reasonerMap[approval.approvalType] || 'unknown';
}

export function aggregateDiffs(approvals: ApprovalContext[]): {
  combined: string;
  tabs: DiffTab[];
} {
  const tabs: DiffTab[] = [];
  const diffs: string[] = [];

  // Sort approvals chronologically
  const sorted = [...approvals].sort(
    (a, b) => new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime()
  );

  for (const approval of sorted) {
    const diff = extractDiffFromApproval(approval);
    if (diff) {
      const separator = `# --- Changes from ${approval.approvalType} ---\n`;
      diffs.push(separator + diff);

      tabs.push({
        label: `${approval.approvalType} (${getReasonerName(approval)})`,
        diff: diff,
        executionId: approval.runId,
        reasoner: getReasonerName(approval),
      });
    }
  }

  const combined = diffs.join('\n\n');

  // Truncate if too large
  const lines = combined.split('\n');
  const truncated = lines.length > MAX_COMBINED_LINES
    ? lines.slice(0, MAX_COMBINED_LINES).join('\n') + '\n\n# ... (truncated - diff too large)'
    : combined;

  return { combined: truncated, tabs };
}
