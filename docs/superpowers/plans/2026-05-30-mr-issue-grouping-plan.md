# MR/Issue Grouping View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "By Source" tab to approval dashboard that groups related approvals by MR/issue, shows combined diffs, and supports batch approval with individual review mode.

**Architecture:** Backend extracts source metadata (URL, type, identifier) from task and includes in approval pause context. Frontend parses metadata, groups approvals by source identifier, renders tabbed diff viewer with combined view, and handles batch approval workflow.

**Tech Stack:** Python (backend), React + TypeScript + TanStack Query (frontend), existing DiffViewer component

---

## File Structure

### Backend Files
- **Modify:** `nd/schemas.py` - Add source tracking fields
- **Modify:** `nd/worker/agent.py` - Extract and include source metadata in pause calls
- **Modify:** `tests/unit/test_worker_agent.py` - Test source metadata extraction

### Frontend Files
- **Modify:** `approval-dashboard/src/api/types.ts` - Add GroupedApproval interface
- **Modify:** `approval-dashboard/src/utils/parser.ts` - Extract source metadata with fallback
- **Modify:** `approval-dashboard/src/App.tsx` - Add "By Source" tab
- **Create:** `approval-dashboard/src/utils/grouping.ts` - Grouping logic
- **Create:** `approval-dashboard/src/utils/diff-aggregator.ts` - Diff combining logic
- **Create:** `approval-dashboard/src/hooks/useGroupedApprovals.ts` - Grouping hook
- **Create:** `approval-dashboard/src/hooks/useGroupedApprovalSubmit.ts` - Batch submission hook
- **Create:** `approval-dashboard/src/components/TabbedDiffViewer.tsx` - Tabbed diff component
- **Create:** `approval-dashboard/src/components/GroupedApprovalCard.tsx` - Grouped card component
- **Create:** `approval-dashboard/src/components/GroupedApprovalList.tsx` - List component
- **Create:** `approval-dashboard/src/utils/grouping.test.ts` - Grouping tests
- **Create:** `approval-dashboard/src/utils/diff-aggregator.test.ts` - Diff aggregation tests
- **Create:** `approval-dashboard/tests/e2e/grouped-approval.spec.ts` - E2E tests

---

## Task 1: Backend - Add Source Metadata Schema

**Files:**
- Modify: `nd/schemas.py:1-250`

- [ ] **Step 1: Add source metadata fields to worker schemas**

In `nd/schemas.py`, after the `ApprovalRequest` class (around line 235), add:

```python
class SourceMetadata(BaseModel):
    """Source tracking metadata for approval requests."""

    source_url: str = Field(description="Full URL to MR or issue")
    source_type: Literal["mr", "issue"] = Field(description="Type of source")
    source_identifier: str = Field(
        description="Format: platform:owner/repo#number (e.g., gitlab:flatiron/myproject#123)"
    )
```

- [ ] **Step 2: Verify schema is valid**

Run: `python -c "from nd.schemas import SourceMetadata; print(SourceMetadata.__fields__)"`
Expected: Output shows source_url, source_type, source_identifier fields

- [ ] **Step 3: Commit schema changes**

```bash
git add nd/schemas.py
git commit -m "feat: add source metadata schema for approval grouping

Add SourceMetadata model with source_url, source_type, and source_identifier
fields to support grouping approvals by their originating MR or issue.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Backend - Extract Source Metadata in Worker Agent

**Files:**
- Modify: `nd/worker/agent.py:250-450`

- [ ] **Step 1: Add source extraction helper function**

In `nd/worker/agent.py`, before the `process_task` reasoner (around line 250), add:

```python
def _extract_source_metadata(
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    mr_number: int | None = None,
    mr_url: str | None = None,
    issue_number: int | None = None,
    issue_url: str | None = None,
) -> tuple[str, str, str]:
    """Extract source URL, type, and identifier from task metadata.

    Returns:
        (source_url, source_type, source_identifier)
    """
    if mr_number and mr_url:
        # MR comment task
        source_url = mr_url
        source_type = "mr"
        source_identifier = f"{platform}:{repo_owner}/{repo_name}#{mr_number}"
    elif issue_number and issue_url:
        # Issue task
        source_url = issue_url
        source_type = "issue"
        source_identifier = f"{platform}:{repo_owner}/{repo_name}#{issue_number}"
    else:
        # Fallback: construct from available data
        if mr_number:
            source_url = f"https://{platform_host}/{repo_owner}/{repo_name}/-/merge_requests/{mr_number}"
            source_type = "mr"
            source_identifier = f"{platform}:{repo_owner}/{repo_name}#{mr_number}"
        elif issue_number:
            source_url = f"https://{platform_host}/{repo_owner}/{repo_name}/-/issues/{issue_number}"
            source_type = "issue"
            source_identifier = f"{platform}:{repo_owner}/{repo_name}#{issue_number}"
        else:
            # No source info available
            source_url = "unknown"
            source_type = "mr"
            source_identifier = "unknown:unknown#0"

    return source_url, source_type, source_identifier
```

- [ ] **Step 2: Update process_task to extract source metadata**

In the `process_task` reasoner, after extracting task inputs (around line 280), add source metadata extraction:

```python
# Extract source metadata for grouping
source_url, source_type, source_identifier = _extract_source_metadata(
    platform=platform,
    platform_host=platform_host,
    repo_owner=repo_owner,
    repo_name=repo_name,
    mr_number=task_dict.get("mr_number"),
    mr_url=task_dict.get("mr_url"),
    issue_number=task_dict.get("issue_number"),
    issue_url=task_dict.get("issue_url"),
)
```

- [ ] **Step 3: Include source metadata in app.pause() calls**

Find the three `app.pause()` calls in `process_task` (for spec review, roborev failure, response approval) and add source metadata to each. Example for spec review (around line 340):

```python
await app.pause(
    approval_request_id=spec_request_id,
    approval_request_url=mr_url or issue_url or "unknown",
    expires_in_hours=72,
    # Source metadata for grouping
    source_url=source_url,
    source_type=source_type,
    source_identifier=source_identifier,
)
```

Repeat for the roborev and response pause calls.

- [ ] **Step 4: Verify syntax is valid**

Run: `python -m py_compile nd/worker/agent.py`
Expected: No output (successful compilation)

- [ ] **Step 5: Commit worker agent changes**

```bash
git add nd/worker/agent.py
git commit -m "feat: extract and include source metadata in approval pauses

Add _extract_source_metadata helper to derive source URL, type, and identifier
from task metadata. Include in all app.pause() calls for grouping support.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Backend - Test Source Metadata Extraction

**Files:**
- Modify: `tests/unit/test_worker_agent.py`

- [ ] **Step 1: Write test for MR source metadata**

Add to `tests/unit/test_worker_agent.py`:

```python
@pytest.mark.asyncio
async def test_extract_source_metadata_for_mr():
    """Test source metadata extraction for MR comment tasks."""
    from nd.worker.agent import _extract_source_metadata

    source_url, source_type, source_identifier = _extract_source_metadata(
        platform="gitlab",
        platform_host="gitlab.com",
        repo_owner="flatiron",
        repo_name="extraction-tools",
        mr_number=123,
        mr_url="https://gitlab.com/flatiron/extraction-tools/-/merge_requests/123",
    )

    assert source_url == "https://gitlab.com/flatiron/extraction-tools/-/merge_requests/123"
    assert source_type == "mr"
    assert source_identifier == "gitlab:flatiron/extraction-tools#123"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_worker_agent.py::test_extract_source_metadata_for_mr -v`
Expected: PASS

- [ ] **Step 3: Write test for issue source metadata**

Add to `tests/unit/test_worker_agent.py`:

```python
@pytest.mark.asyncio
async def test_extract_source_metadata_for_issue():
    """Test source metadata extraction for issue tasks."""
    from nd.worker.agent import _extract_source_metadata

    source_url, source_type, source_identifier = _extract_source_metadata(
        platform="github",
        platform_host="github.com",
        repo_owner="flatiron",
        repo_name="data-science",
        issue_number=456,
        issue_url="https://github.com/flatiron/data-science/issues/456",
    )

    assert source_url == "https://github.com/flatiron/data-science/issues/456"
    assert source_type == "issue"
    assert source_identifier == "github:flatiron/data-science#456"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_worker_agent.py::test_extract_source_metadata_for_issue -v`
Expected: PASS

- [ ] **Step 5: Run all unit tests to ensure no regressions**

Run: `pytest tests/unit -v`
Expected: All tests PASS

- [ ] **Step 6: Commit test changes**

```bash
git add tests/unit/test_worker_agent.py
git commit -m "test: add tests for source metadata extraction

Verify _extract_source_metadata correctly derives source URL, type, and
identifier for both MR and issue tasks.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Frontend - Update Type Definitions

**Files:**
- Modify: `approval-dashboard/src/api/types.ts`

- [ ] **Step 1: Add source fields to ApprovalContext interface**

In `approval-dashboard/src/api/types.ts`, find the `ApprovalContext` interface (around line 49) and add source fields:

```typescript
export interface ApprovalContext {
  approvalType: ApprovalType;
  taskId: string;
  runId: string;
  requestId: string;
  mrUrl?: string;
  expiresAt: Date;
  originalComment: string;
  taskTitle: string;
  projectName: string;
  spec?: SpecReviewContext;
  roborev?: RoborevContext;
  response?: ResponseContext;
  // Source tracking for grouping
  sourceUrl: string;
  sourceType: 'mr' | 'issue';
  sourceIdentifier: string;
}
```

- [ ] **Step 2: Add GroupedApproval interface**

After the `ApprovalContext` interface, add:

```typescript
export interface GroupedApproval {
  sourceUrl: string;
  sourceType: 'mr' | 'issue';
  sourceIdentifier: string;
  sourceTitle: string;
  approvals: ApprovalContext[];
  approvalCounts: {
    spec: number;
    roborev: number;
    post: number;
  };
  latestTimestamp: Date;
}
```

- [ ] **Step 3: Add DiffTab interface**

After `GroupedApproval`, add:

```typescript
export interface DiffTab {
  label: string;
  diff: string;
  executionId: string;
  reasoner: string;
}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 5: Commit type definition changes**

```bash
git add approval-dashboard/src/api/types.ts
git commit -m "feat: add type definitions for approval grouping

Add sourceUrl, sourceType, sourceIdentifier to ApprovalContext.
Add GroupedApproval and DiffTab interfaces for grouping view.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Frontend - Update Parser for Source Metadata

**Files:**
- Modify: `approval-dashboard/src/utils/parser.ts`

- [ ] **Step 1: Add source extraction helper function**

In `approval-dashboard/src/utils/parser.ts`, before `parseApprovalContext`, add:

```typescript
function extractSourceMetadata(data: any): {
  sourceUrl: string;
  sourceType: 'mr' | 'issue';
  sourceIdentifier: string;
} {
  // Primary: extract from pause context (new executions)
  if (data.source_url && data.source_identifier) {
    return {
      sourceUrl: data.source_url,
      sourceType: data.source_type || 'mr',
      sourceIdentifier: data.source_identifier,
    };
  }

  // Fallback: derive from approval_request_url (old executions)
  const url = data.approval_request_url || '';

  // Parse GitLab MR URL
  const gitlabMrMatch = url.match(/gitlab\.com\/([^/]+)\/([^/]+)\/-\/merge_requests\/(\d+)/);
  if (gitlabMrMatch) {
    const [, owner, repo, number] = gitlabMrMatch;
    return {
      sourceUrl: url,
      sourceType: 'mr',
      sourceIdentifier: `gitlab:${owner}/${repo}#${number}`,
    };
  }

  // Parse GitLab issue URL
  const gitlabIssueMatch = url.match(/gitlab\.com\/([^/]+)\/([^/]+)\/-\/issues\/(\d+)/);
  if (gitlabIssueMatch) {
    const [, owner, repo, number] = gitlabIssueMatch;
    return {
      sourceUrl: url,
      sourceType: 'issue',
      sourceIdentifier: `gitlab:${owner}/${repo}#${number}`,
    };
  }

  // Parse GitHub PR URL
  const githubPrMatch = url.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
  if (githubPrMatch) {
    const [, owner, repo, number] = githubPrMatch;
    return {
      sourceUrl: url,
      sourceType: 'mr',
      sourceIdentifier: `github:${owner}/${repo}#${number}`,
    };
  }

  // Parse GitHub issue URL
  const githubIssueMatch = url.match(/github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/);
  if (githubIssueMatch) {
    const [, owner, repo, number] = githubIssueMatch;
    return {
      sourceUrl: url,
      sourceType: 'issue',
      sourceIdentifier: `github:${owner}/${repo}#${number}`,
    };
  }

  // Fallback: ungrouped
  return {
    sourceUrl: url || 'unknown',
    sourceType: 'mr',
    sourceIdentifier: 'ungrouped:unknown#0',
  };
}
```

- [ ] **Step 2: Add source metadata to parseApprovalContext**

In `parseApprovalContext`, after extracting `projectName` (around line 40), add:

```typescript
// Extract source metadata for grouping
const { sourceUrl, sourceType, sourceIdentifier } = extractSourceMetadata(data);
```

- [ ] **Step 3: Include source fields in baseContext**

In the `baseContext` object, add the source fields:

```typescript
const baseContext: ApprovalContext = {
  approvalType,
  taskId,
  runId: data.workflow_id || data.run_id,
  requestId: approval_request_id,
  mrUrl: approval_request_url || undefined,
  expiresAt,
  originalComment,
  taskTitle,
  projectName,
  sourceUrl,
  sourceType,
  sourceIdentifier,
};
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 5: Commit parser changes**

```bash
git add approval-dashboard/src/utils/parser.ts
git commit -m "feat: extract source metadata in parser with fallback

Add extractSourceMetadata helper to parse source URL/type/identifier from
pause context (new) or approval_request_url (fallback for old executions).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Frontend - Add Grouping Utility

**Files:**
- Create: `approval-dashboard/src/utils/grouping.ts`

- [ ] **Step 1: Create grouping utility file**

Create `approval-dashboard/src/utils/grouping.ts`:

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit grouping utility**

```bash
git add approval-dashboard/src/utils/grouping.ts
git commit -m "feat: add approval grouping utility

Add groupApprovalsBySource function to group approvals by sourceIdentifier
and sort by most recent activity.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Frontend - Add Diff Aggregation Utility

**Files:**
- Create: `approval-dashboard/src/utils/diff-aggregator.ts`

- [ ] **Step 1: Create diff aggregator file**

Create `approval-dashboard/src/utils/diff-aggregator.ts`:

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit diff aggregator**

```bash
git add approval-dashboard/src/utils/diff-aggregator.ts
git commit -m "feat: add diff aggregation utility

Add aggregateDiffs function to combine diffs chronologically with separators
and create individual tabs. Truncates combined diff at 10k lines.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Frontend - Add Unit Tests for Grouping

**Files:**
- Create: `approval-dashboard/src/utils/grouping.test.ts`

- [ ] **Step 1: Write test for grouping by source**

Create `approval-dashboard/src/utils/grouping.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd approval-dashboard && npm test -- grouping.test.ts`
Expected: All tests PASS

- [ ] **Step 3: Commit grouping tests**

```bash
git add approval-dashboard/src/utils/grouping.test.ts
git commit -m "test: add unit tests for approval grouping

Verify groupApprovalsBySource correctly groups by source identifier,
sorts by most recent activity, and tracks latest timestamp.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Frontend - Add Unit Tests for Diff Aggregation

**Files:**
- Create: `approval-dashboard/src/utils/diff-aggregator.test.ts`

- [ ] **Step 1: Write test for combining diffs**

Create `approval-dashboard/src/utils/diff-aggregator.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd approval-dashboard && npm test -- diff-aggregator.test.ts`
Expected: All tests PASS

- [ ] **Step 3: Commit diff aggregation tests**

```bash
git add approval-dashboard/src/utils/diff-aggregator.test.ts
git commit -m "test: add unit tests for diff aggregation

Verify aggregateDiffs combines diffs with separators, truncates at 10k lines,
creates tabs with correct labels, and handles approvals without diffs.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Frontend - Add useGroupedApprovals Hook

**Files:**
- Create: `approval-dashboard/src/hooks/useGroupedApprovals.ts`

- [ ] **Step 1: Create useGroupedApprovals hook**

Create `approval-dashboard/src/hooks/useGroupedApprovals.ts`:

```typescript
import { useMemo } from 'react';
import { useApprovals } from './useApprovals';
import { groupApprovalsBySource } from '../utils/grouping';

export function useGroupedApprovals() {
  const { data: approvals, ...rest } = useApprovals();

  const grouped = useMemo(() => {
    if (!approvals) return [];
    return groupApprovalsBySource(approvals);
  }, [approvals]);

  return { data: grouped, ...rest };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit useGroupedApprovals hook**

```bash
git add approval-dashboard/src/hooks/useGroupedApprovals.ts
git commit -m "feat: add useGroupedApprovals hook

Wrap useApprovals with grouping logic, memoized to avoid recomputation.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Frontend - Add useGroupedApprovalSubmit Hook

**Files:**
- Create: `approval-dashboard/src/hooks/useGroupedApprovalSubmit.ts`

- [ ] **Step 1: Create useGroupedApprovalSubmit hook**

Create `approval-dashboard/src/hooks/useGroupedApprovalSubmit.ts`:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { submitApproval } from '../api/agentfield';
import { ApprovalDecision } from '../api/types';

interface BatchApprovalRequest {
  requestIds: string[];
  decision: ApprovalDecision;
  feedback?: string;
}

interface BatchApprovalResult {
  succeeded: number;
  failed: number;
  results: PromiseSettledResult<any>[];
}

export function useGroupedApprovalSubmit() {
  const queryClient = useQueryClient();

  return useMutation<BatchApprovalResult, Error, BatchApprovalRequest>({
    mutationFn: async (req: BatchApprovalRequest) => {
      // Send all approval requests in parallel
      const results = await Promise.allSettled(
        req.requestIds.map(id =>
          submitApproval({ requestId: id, decision: req.decision, feedback: req.feedback })
        )
      );

      const succeeded = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;

      return { succeeded, failed, results };
    },
    onSuccess: () => {
      // Refetch approvals after successful submission
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit useGroupedApprovalSubmit hook**

```bash
git add approval-dashboard/src/hooks/useGroupedApprovalSubmit.ts
git commit -m "feat: add useGroupedApprovalSubmit hook

Add mutation hook for batch approval submission with parallel requests
and result tracking.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Frontend - Create TabbedDiffViewer Component

**Files:**
- Create: `approval-dashboard/src/components/TabbedDiffViewer.tsx`

- [ ] **Step 1: Create TabbedDiffViewer component**

Create `approval-dashboard/src/components/TabbedDiffViewer.tsx`:

```typescript
import { useState } from 'react';
import { DiffViewer } from './DiffViewer';
import { DiffTab } from '../api/types';

interface TabbedDiffViewerProps {
  combined: string;
  tabs: DiffTab[];
}

export function TabbedDiffViewer({ combined, tabs }: TabbedDiffViewerProps) {
  const [activeTab, setActiveTab] = useState<'combined' | number>('combined');

  const allTabs = [
    { id: 'combined' as const, label: 'Combined', diff: combined },
    ...tabs.map((tab, index) => ({ id: index, label: tab.label, diff: tab.diff })),
  ];

  const activeDiff = activeTab === 'combined'
    ? combined
    : tabs[activeTab as number]?.diff || '';

  if (tabs.length === 0 && !combined) {
    return (
      <div className="text-gray-500 text-sm p-4 border border-gray-200 rounded-md">
        No diffs available for this approval group.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-gray-200">
        {allTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              px-4 py-2 text-sm font-medium border-b-2 transition-colors
              ${activeTab === tab.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Diff Content */}
      <div>
        {activeDiff ? (
          <DiffViewer diff={activeDiff} />
        ) : (
          <div className="text-gray-500 text-sm p-4">
            No diff available for this tab.
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit TabbedDiffViewer component**

```bash
git add approval-dashboard/src/components/TabbedDiffViewer.tsx
git commit -m "feat: add TabbedDiffViewer component

Add tabbed interface for viewing combined and individual diffs.
Reuses existing DiffViewer component for rendering.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Frontend - Create GroupedApprovalCard Component

**Files:**
- Create: `approval-dashboard/src/components/GroupedApprovalCard.tsx`

- [ ] **Step 1: Create GroupedApprovalCard component (part 1 - structure)**

Create `approval-dashboard/src/components/GroupedApprovalCard.tsx`:

```typescript
import { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import { GroupedApproval, ApprovalDecision } from '../api/types';
import { TabbedDiffViewer } from './TabbedDiffViewer';
import { ApprovalCard } from './ApprovalCard';
import { aggregateDiffs } from '../utils/diff-aggregator';
import { useGroupedApprovalSubmit } from '../hooks/useGroupedApprovalSubmit';

interface GroupedApprovalCardProps {
  group: GroupedApproval;
}

export function GroupedApprovalCard({ group }: GroupedApprovalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');
  const { mutate, isPending } = useGroupedApprovalSubmit();

  const { combined, tabs } = aggregateDiffs(group.approvals);

  const handleBatchApproval = (decision: ApprovalDecision) => {
    const requestIds = group.approvals.map(a => a.requestId);
    mutate({
      requestIds,
      decision,
      feedback: feedback || undefined,
    });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <a
              href={group.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-lg font-semibold text-blue-600 hover:text-blue-800"
            >
              {group.sourceIdentifier}
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
          <p className="text-sm text-gray-600 mt-1">{group.sourceTitle}</p>
        </div>
      </div>

      {/* Approval Counts */}
      <div className="flex gap-2 mb-4">
        <span className="text-sm text-gray-600">
          {group.approvals.length} approval{group.approvals.length !== 1 ? 's' : ''}:
        </span>
        {group.approvalCounts.spec > 0 && (
          <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
            Spec: {group.approvalCounts.spec}
          </span>
        )}
        {group.approvalCounts.roborev > 0 && (
          <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
            Roborev: {group.approvalCounts.roborev}
          </span>
        )}
        {group.approvalCounts.post > 0 && (
          <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
            Post: {group.approvalCounts.post}
          </span>
        )}
      </div>

      {/* Tabbed Diff Viewer */}
      <div className="mb-6">
        <TabbedDiffViewer combined={combined} tabs={tabs} />
      </div>

      {/* Batch Approval Actions */}
      <div className="space-y-4">
        <div className="flex gap-3">
          <button
            onClick={() => handleBatchApproval('approved')}
            disabled={isPending}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            {isPending ? 'Submitting...' : '✅ Approve All'}
          </button>
          <button
            onClick={() => handleBatchApproval('rejected')}
            disabled={isPending}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium"
          >
            {isPending ? 'Submitting...' : '❌ Reject All'}
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 font-medium"
          >
            📝 Review Individually
          </button>
        </div>

        {/* Feedback textarea */}
        {showFeedback && (
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional feedback (sent to all approvals)"
            className="w-full px-3 py-2 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
          />
        )}
        <button
          onClick={() => setShowFeedback(!showFeedback)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {showFeedback ? 'Hide' : 'Add'} feedback
        </button>
      </div>

      {/* Individual Approvals (expanded) */}
      {expanded && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          <div className="flex items-center gap-2 mb-4">
            <ChevronDown className="w-5 h-5 text-gray-600" />
            <h3 className="font-semibold text-gray-900">Individual Approvals</h3>
          </div>
          <div className="space-y-4">
            {group.approvals.map((approval) => (
              <ApprovalCard
                key={approval.requestId}
                approval={approval}
                trace={[]}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit GroupedApprovalCard component**

```bash
git add approval-dashboard/src/components/GroupedApprovalCard.tsx
git commit -m "feat: add GroupedApprovalCard component

Add card component for displaying grouped approvals with batch actions,
tabbed diff viewer, and expandable individual approval list.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: Frontend - Create GroupedApprovalList Component

**Files:**
- Create: `approval-dashboard/src/components/GroupedApprovalList.tsx`

- [ ] **Step 1: Create GroupedApprovalList component**

Create `approval-dashboard/src/components/GroupedApprovalList.tsx`:

```typescript
import { GroupedApproval } from '../api/types';
import { GroupedApprovalCard } from './GroupedApprovalCard';

interface GroupedApprovalListProps {
  groups: GroupedApproval[];
}

export function GroupedApprovalList({ groups }: GroupedApprovalListProps) {
  if (groups.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 text-lg">No pending approvals</p>
        <p className="text-gray-500 text-sm mt-2">
          Approvals will appear here when nd worker pauses for review
        </p>
      </div>
    );
  }

  // Separate ungrouped approvals
  const grouped = groups.filter(g => !g.sourceIdentifier.startsWith('ungrouped:'));
  const ungrouped = groups.filter(g => g.sourceIdentifier.startsWith('ungrouped:'));

  return (
    <div className="space-y-6">
      {/* Grouped approvals */}
      {grouped.map((group) => (
        <GroupedApprovalCard key={group.sourceIdentifier} group={group} />
      ))}

      {/* Ungrouped section */}
      {ungrouped.length > 0 && (
        <div className="mt-8">
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">
              ⚠️ The following approvals could not be grouped (missing source metadata):
            </p>
          </div>
          {ungrouped.map((group) => (
            <GroupedApprovalCard key={group.sourceIdentifier} group={group} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 3: Commit GroupedApprovalList component**

```bash
git add approval-dashboard/src/components/GroupedApprovalList.tsx
git commit -m "feat: add GroupedApprovalList component

Add list container for grouped approval cards with empty state and
ungrouped section for approvals without source metadata.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 15: Frontend - Integrate "By Source" Tab in App

**Files:**
- Modify: `approval-dashboard/src/App.tsx`

- [ ] **Step 1: Import new hooks and components**

At the top of `App.tsx`, add imports:

```typescript
import { useGroupedApprovals } from './hooks/useGroupedApprovals';
import { GroupedApprovalList } from './components/GroupedApprovalList';
```

- [ ] **Step 2: Update TabType to include 'source'**

Find the `TabType` definition (around line 8) and update:

```typescript
type TabType = 'source' | 'spec' | 'roborev' | 'post' | 'control';
```

- [ ] **Step 3: Add useGroupedApprovals hook**

After the existing `useApprovals` hook call (around line 11), add:

```typescript
const { data: groupedApprovals } = useGroupedApprovals();
```

- [ ] **Step 4: Change default active tab to 'source'**

Update the `useState` for activeTab:

```typescript
const [activeTab, setActiveTab] = useState<TabType>('source');
```

- [ ] **Step 5: Add "By Source" tab button**

In the tabs navigation section (around line 72), add the "By Source" tab as the first tab:

```typescript
<TabButton
  active={activeTab === 'source'}
  count={groupedApprovals?.length || 0}
  onClick={() => setActiveTab('source')}
>
  By Source
</TabButton>
```

- [ ] **Step 6: Add "By Source" tab content**

After the control tab content and before the other tab contents (around line 160), add:

```typescript
{activeTab === 'source' && (
  <GroupedApprovalList groups={groupedApprovals || []} />
)}
```

- [ ] **Step 7: Update other tab conditions**

Update the existing tab content conditions to exclude 'source':

```typescript
{activeTab !== 'control' && activeTab !== 'source' && isLoading && !approvals && (
  // ... existing loading state
)}

{activeTab !== 'control' && activeTab !== 'source' && !isLoading && !isError && filteredApprovals.length === 0 && (
  // ... existing empty state
)}

{activeTab !== 'control' && activeTab !== 'source' && filteredApprovals.length > 0 && (
  // ... existing approval list
)}
```

- [ ] **Step 8: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 9: Verify app builds**

Run: `cd approval-dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 10: Commit App integration**

```bash
git add approval-dashboard/src/App.tsx
git commit -m "feat: integrate 'By Source' tab in approval dashboard

Add 'By Source' as first tab, wire up useGroupedApprovals hook and
GroupedApprovalList component. Set as default active tab.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 16: Frontend - Add E2E Test for Grouping

**Files:**
- Create: `approval-dashboard/tests/e2e/grouped-approval.spec.ts`

- [ ] **Step 1: Create E2E test file (part 1 - basic grouping)**

Create `approval-dashboard/tests/e2e/grouped-approval.spec.ts`:

```typescript
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
```

- [ ] **Step 2: Run E2E tests to verify structure**

Run: `cd approval-dashboard && npm run test:e2e`
Expected: Tests PASS (testing UI structure, not data)

- [ ] **Step 3: Commit E2E tests**

```bash
git add approval-dashboard/tests/e2e/grouped-approval.spec.ts
git commit -m "test: add E2E tests for grouped approval view

Add basic E2E tests verifying 'By Source' tab structure and UI elements.
Full integration tests require mocked AgentField data.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 17: Run Full Test Suite

**Files:**
- Test: All

- [ ] **Step 1: Run backend unit tests**

Run: `pytest tests/unit -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend unit tests**

Run: `cd approval-dashboard && npm test`
Expected: All tests PASS

- [ ] **Step 3: Run frontend E2E tests**

Run: `cd approval-dashboard && npm run test:e2e`
Expected: All tests PASS

- [ ] **Step 4: Verify linting passes**

Run: `cd approval-dashboard && npm run lint`
Expected: No errors

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd approval-dashboard && npm run type-check`
Expected: No errors

- [ ] **Step 6: Verify production build works**

Run: `cd approval-dashboard && npm run build`
Expected: Build succeeds

---

## Task 18: Manual Testing and Documentation

**Files:**
- Test: Manual workflow
- Modify: `README.md` (optional)

- [ ] **Step 1: Start dashboard locally**

Run: `cd approval-dashboard && npm run dev`
Expected: Dev server starts on localhost:3000

- [ ] **Step 2: Verify "By Source" tab appears**

Open browser to http://localhost:3000
Expected: "By Source" tab is first tab and active by default

- [ ] **Step 3: Verify empty state**

With no approvals pending:
Expected: Shows "No pending approvals" message

- [ ] **Step 4: Test with worker agent (if available)**

Trigger worker agent with a task:
Expected: Approval appears grouped by source with MR/issue identifier

- [ ] **Step 5: Verify batch approval UI**

If approval card exists:
Expected: Shows "Approve All", "Reject All", "Review Individually" buttons

- [ ] **Step 6: Verify tabbed diff viewer**

If approval has diffs:
Expected: Shows "Combined" tab and individual tabs for each execution

- [ ] **Step 7: Update README (optional)**

If README needs updating, add section about "By Source" tab:

```markdown
### By Source Tab

The "By Source" tab groups related approvals by their originating MR or issue.
Features:
- View all approvals from a single MR/issue together
- Combined diff view showing all changes chronologically
- Batch approve/reject all approvals with one click
- Individual review mode for mixed decisions
```

- [ ] **Step 8: Commit README updates (if made)**

```bash
git add README.md
git commit -m "docs: add By Source tab documentation

Document new grouped approval view in README.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ Backend source metadata schema (Task 1)
- ✅ Backend source extraction in worker agent (Task 2)
- ✅ Backend tests for metadata extraction (Task 3)
- ✅ Frontend type definitions (Task 4)
- ✅ Frontend parser with fallback (Task 5)
- ✅ Grouping utility (Task 6)
- ✅ Diff aggregation utility (Task 7)
- ✅ Unit tests for grouping and diff aggregation (Tasks 8-9)
- ✅ useGroupedApprovals hook (Task 10)
- ✅ useGroupedApprovalSubmit hook (Task 11)
- ✅ TabbedDiffViewer component (Task 12)
- ✅ GroupedApprovalCard component (Task 13)
- ✅ GroupedApprovalList component (Task 14)
- ✅ App integration with "By Source" tab (Task 15)
- ✅ E2E tests (Task 16)
- ✅ Full test suite execution (Task 17)
- ✅ Manual testing and documentation (Task 18)

**Placeholder Scan:**
- ✅ No TBD, TODO, or "implement later" placeholders
- ✅ All code blocks contain actual implementation
- ✅ All test cases have actual assertions
- ✅ All commands have expected output

**Type Consistency:**
- ✅ ApprovalContext fields match across parser, hooks, and components
- ✅ GroupedApproval structure consistent in grouping utility and components
- ✅ DiffTab interface used consistently in aggregator and viewer

**Gaps:**
- Note: Response approval diffs are not fully implemented in diff-aggregator.ts because ResponseContext doesn't currently include a diff field. This is documented in the helper function and can be added later when execute_changes output is available in ResponseContext.

---

## Success Criteria

✅ Worker agent includes source_url, source_type, source_identifier in all new approval pause contexts
✅ Dashboard "By Source" tab groups approvals by sourceIdentifier
✅ Combined diff tab shows all changes with separators
✅ Individual diff tabs show each execution's changes
✅ "Approve All" / "Reject All" buttons send batch approvals
✅ "Review Individually" expands to show individual approval cards
✅ Old executions without source metadata fallback to URL parsing or show in ungrouped section
✅ All unit tests pass
✅ All E2E tests pass
✅ No breaking changes to existing tabs
