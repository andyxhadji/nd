import { ApprovalContext, GroupedApproval } from '../api/types';

export function groupApprovalsBySource(
  approvals: ApprovalContext[]
): GroupedApproval[] {
  const groups = new Map<string, GroupedApproval>();

  for (const approval of approvals) {
    const key = approval.sourceIdentifier;

    if (!groups.has(key)) {
      groups.set(key, {
        sourceUrl: approval.sourceUrl,
        sourceType: approval.sourceType,
        sourceIdentifier: approval.sourceIdentifier,
        sourceTitle: approval.taskTitle,
        approvals: [],
        approvalCounts: { spec: 0, roborev: 0, post: 0 },
        latestTimestamp: new Date(approval.expiresAt),
      });
    }

    const group = groups.get(key)!;
    group.approvals.push(approval);
    group.approvalCounts[approval.approvalType]++;

    // Update latest timestamp
    const approvalTime = new Date(approval.expiresAt);
    if (approvalTime > group.latestTimestamp) {
      group.latestTimestamp = approvalTime;
    }
  }

  // Sort groups by most recent activity first
  return Array.from(groups.values()).sort(
    (a, b) => b.latestTimestamp.getTime() - a.latestTimestamp.getTime()
  );
}
