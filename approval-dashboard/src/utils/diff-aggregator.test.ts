import { describe, it, expect } from 'vitest';
import { aggregateDiffs } from './diff-aggregator';
import { ApprovalContext, RoborevContext } from '../api/types';

function createApprovalWithDiff(
  approvalType: 'spec' | 'roborev' | 'post',
  diff: string
): ApprovalContext {
  const roborev: RoborevContext = {
    passed: false,
    iterations: 1,
    findings: [],
    filesChanged: [],
    commitSha: 'abc123',
    diff: diff,
  };

  return {
    approvalType,
    taskId: 'task-1',
    runId: 'run-1',
    requestId: 'req-1',
    expiresAt: new Date(),
    originalComment: 'test',
    taskTitle: 'Test',
    projectName: 'test',
    sourceUrl: 'https://test.com',
    sourceType: 'mr',
    sourceIdentifier: 'test:test#1',
    roborev: approvalType === 'roborev' ? roborev : undefined,
  };
}

describe('aggregateDiffs', () => {
  it('combines diffs with separators', () => {
    const approvals = [
      createApprovalWithDiff('roborev', 'diff --git a/file1.py\n+line1'),
      createApprovalWithDiff('roborev', 'diff --git a/file2.py\n+line2'),
    ];

    const { combined, tabs } = aggregateDiffs(approvals);

    expect(combined).toContain('# --- Changes from roborev ---');
    expect(combined).toContain('diff --git a/file1.py');
    expect(combined).toContain('diff --git a/file2.py');
    expect(tabs).toHaveLength(2);
  });

  it('truncates combined diff at 10000 lines', () => {
    const hugeDiff = 'line\n'.repeat(15000);
    const approvals = [createApprovalWithDiff('roborev', hugeDiff)];

    const { combined } = aggregateDiffs(approvals);

    const lines = combined.split('\n');
    expect(lines.length).toBeLessThanOrEqual(10002); // 10000 + separator + truncation
    expect(combined).toContain('(truncated');
  });

  it('creates tabs with correct labels', () => {
    const approvals = [
      createApprovalWithDiff('roborev', 'diff1'),
    ];

    const { tabs } = aggregateDiffs(approvals);

    expect(tabs[0].label).toBe('roborev (execute_changes)');
    expect(tabs[0].diff).toBe('diff1');
    expect(tabs[0].reasoner).toBe('execute_changes');
  });

  it('handles approvals without diffs', () => {
    const approval: ApprovalContext = {
      approvalType: 'spec',
      taskId: 'task-1',
      runId: 'run-1',
      requestId: 'req-1',
      expiresAt: new Date(),
      originalComment: 'test',
      taskTitle: 'Test',
      projectName: 'test',
      sourceUrl: 'https://test.com',
      sourceType: 'mr',
      sourceIdentifier: 'test:test#1',
    };

    const { combined, tabs } = aggregateDiffs([approval]);

    expect(combined).toBe('');
    expect(tabs).toHaveLength(0);
  });
});
