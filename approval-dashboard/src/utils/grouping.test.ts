import { describe, it, expect } from 'vitest';
import { groupApprovalsBySource } from './grouping';
import { ApprovalContext } from '../api/types';

function createApproval(overrides: Partial<ApprovalContext>): ApprovalContext {
  return {
    approvalType: 'spec',
    taskId: 'task-1',
    runId: 'run-1',
    requestId: 'req-1',
    expiresAt: new Date(),
    originalComment: 'test comment',
    taskTitle: 'Test Task',
    projectName: 'test-project',
    sourceUrl: 'https://gitlab.com/test/repo/-/merge_requests/123',
    sourceType: 'mr',
    sourceIdentifier: 'gitlab:test/repo#123',
    ...overrides,
  };
}

describe('groupApprovalsBySource', () => {
  it('groups approvals by source identifier', () => {
    const approvals = [
      createApproval({ sourceIdentifier: 'gitlab:org/repo#123', approvalType: 'spec' }),
      createApproval({ sourceIdentifier: 'gitlab:org/repo#123', approvalType: 'post' }),
      createApproval({ sourceIdentifier: 'gitlab:org/repo#456', approvalType: 'spec' }),
    ];

    const grouped = groupApprovalsBySource(approvals);

    expect(grouped).toHaveLength(2);
    expect(grouped[0].approvals).toHaveLength(2);
    expect(grouped[0].approvalCounts).toEqual({ spec: 1, roborev: 0, post: 1 });
    expect(grouped[1].approvals).toHaveLength(1);
  });

  it('sorts groups by most recent activity', () => {
    const old = new Date('2024-01-01');
    const recent = new Date('2024-12-01');

    const approvals = [
      createApproval({ sourceIdentifier: 'gitlab:org/repo#123', expiresAt: old }),
      createApproval({ sourceIdentifier: 'gitlab:org/repo#456', expiresAt: recent }),
    ];

    const grouped = groupApprovalsBySource(approvals);

    expect(grouped[0].sourceIdentifier).toBe('gitlab:org/repo#456');
    expect(grouped[1].sourceIdentifier).toBe('gitlab:org/repo#123');
  });

  it('uses latest timestamp within a group', () => {
    const old = new Date('2024-01-01');
    const recent = new Date('2024-12-01');

    const approvals = [
      createApproval({ sourceIdentifier: 'gitlab:org/repo#123', expiresAt: old }),
      createApproval({ sourceIdentifier: 'gitlab:org/repo#123', expiresAt: recent }),
    ];

    const grouped = groupApprovalsBySource(approvals);

    expect(grouped[0].latestTimestamp).toEqual(recent);
  });
});
