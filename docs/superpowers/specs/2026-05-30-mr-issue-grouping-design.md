# MR/Issue Grouping View Design

**Date:** 2026-05-30
**Status:** Approved

## Summary

Add a "By Source" tab to the approval dashboard that groups related approvals by their originating MR or issue. This allows engineers to review all work from a single MR/issue in one place, see all diffs together via a tabbed viewer, and batch approve/reject with an option to review individually.

## Problem Statement

The current approval dashboard shows approvals individually across three separate tabs (Spec Reviews, Roborev Failures, Response Approvals). When an MR or issue generates multiple approvals (e.g., a spec review, then execution, then roborev failure, then response), the engineer must:

1. Switch between tabs to find all related approvals
2. Review each approval's diff separately
3. Approve/reject each individually
4. Mentally track which approvals belong to the same source

This creates cognitive overhead and makes it difficult to understand the full scope of changes from a single MR/issue.

## Requirements

### Functional Requirements

1. **Source Grouping**: Group approvals by their originating MR or issue URL
2. **Unified Diff View**: Show all diffs from grouped approvals in a tabbed interface with a "Combined" tab
3. **Batch Approval**: Allow approve/reject for all approvals in a group with a single action
4. **Individual Review Mode**: Toggle to review and approve/reject each approval separately
5. **Backward Compatibility**: Gracefully handle existing executions without source metadata

### Non-Functional Requirements

1. **No Breaking Changes**: Existing approval workflow continues to work unchanged
2. **Performance**: Grouping logic runs efficiently on every 5-second poll
3. **Migration**: Old executions without metadata degrade gracefully

### Out of Scope

- Spec feedback mechanism (deferred to separate feature)
- AgentField API changes for grouped queries
- Historical approval analytics by source

## Proposed Solution

### Architecture Overview

**Backend changes (nd worker agent):**
- Extract source metadata from task (already provided by triage agent)
- Include `source_url`, `source_type`, `source_identifier` in approval pause context
- Metadata flows through AgentField to dashboard automatically

**Frontend changes (approval dashboard):**
- Parse source metadata from AgentField execution details
- Group approvals by `source_identifier` in a new hook
- Add "By Source" tab with grouped card layout
- Build tabbed diff viewer component with combined view
- Add batch approval actions with individual review toggle

**Data Flow:**
```
Triage Agent → Kata Task (includes MR/issue metadata)
     ↓
Worker Agent → Extracts metadata → app.pause(source_url, source_type, source_identifier)
     ↓
AgentField → Stores in pause context
     ↓
Dashboard → Polls → Parses source metadata → Groups approvals → Renders "By Source" tab
```

### Data Model

#### Backend Schema (`nd/schemas.py`)

```python
class ApprovalContext(BaseModel):
    """Extended context for approval requests with source tracking."""

    source_url: str  # Full URL to MR or issue
    source_type: Literal["mr", "issue"]
    source_identifier: str  # Format: "platform:owner/repo#number"
    # Example: "gitlab:flatiron/myproject#123"
```

**Source identifier format:**
- Platform: "github" or "gitlab"
- Owner/repo: from task metadata
- Number: MR or issue number
- Example: `gitlab:flatiron/extraction-tools#456`

#### Frontend Types (`approval-dashboard/src/api/types.ts`)

```typescript
export interface ApprovalContext {
  // ... existing fields (approvalType, taskId, runId, requestId, etc.)
  sourceUrl: string;
  sourceType: 'mr' | 'issue';
  sourceIdentifier: string;
}

export interface GroupedApproval {
  sourceUrl: string;
  sourceType: 'mr' | 'issue';
  sourceIdentifier: string;
  sourceTitle: string;  // Extracted from first approval's task title
  approvals: ApprovalContext[];
  approvalCounts: {
    spec: number;
    roborev: number;
    post: number;
  };
  latestTimestamp: Date;  // For sorting
}
```

### Component Hierarchy

```
App
├── Tabs: ["By Source" (NEW), "Spec Reviews", "Roborev Failures", "Response Approvals", "Agent Control"]
└── Content (when "By Source" active)
    └── GroupedApprovalList
        └── GroupedApprovalCard (per MR/issue)
            ├── Header (source title, link, approval badges)
            ├── TabbedDiffViewer (Combined + individual diffs)
            ├── ApprovalSummary (counts, timestamps)
            ├── BatchApprovalActions (approve/reject all)
            └── IndividualApprovals (expandable when "Review Individually" clicked)
                └── ApprovalCard (reuse existing component)
```

### UI Layout

#### GroupedApprovalCard (Compact - Default State)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔗 flatiron/myproject#123: Add user authentication              │
│                                                         [Expand] │
│ 📊 3 approvals: [Spec: 1] [Roborev: 1] [Post: 1]               │
│                                                                  │
│ [Tabs: Combined | Spec (plan_changes) | Exec | Roborev Fix]    │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ # --- Changes from spec (plan_changes) ---                  ││
│ │ diff --git a/auth.py b/auth.py                              ││
│ │ + def authenticate(user):                                   ││
│ │ ...                                                          ││
│ │ # --- Changes from execution (execute_changes) ---          ││
│ │ diff --git a/auth.py b/auth.py                              ││
│ │ ...                                                          ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│ [✅ Approve All]  [❌ Reject All]  [📝 Review Individually]     │
└─────────────────────────────────────────────────────────────────┘
```

#### GroupedApprovalCard (Expanded - Individual Review Mode)

After clicking "Review Individually", the card expands to show:
- All individual approval cards (reuses existing `ApprovalCard` component)
- Each approval has its own approve/reject buttons and feedback textarea
- Diffs remain in tabbed view at top for easy reference
- Can mix decisions (approve spec, reject response, etc.)

### TabbedDiffViewer Component

**Tab structure:**
- **"Combined"** tab (default) - Shows all diffs concatenated chronologically
- One tab per approval execution:
  - Format: `{approval_type} ({reasoner_name})`
  - Examples: "Spec (plan_changes)", "Execution (execute_changes)", "Roborev Fix (execute_changes)"

**Combined tab logic:**
- Collect diffs from all executions in chronological order
- Add separator comments between each diff:
  ```
  # --- Changes from spec (plan_changes) ---
  # --- Changes from execution (execute_changes) ---
  # --- Changes from roborev iteration 2 (execute_changes) ---
  ```
- Truncate combined diff at 10,000 lines with warning message
- Use existing `DiffViewer` component to render

**Individual tabs:**
- Each shows the diff from one execution
- Reuse existing `DiffViewer` component
- No size limits (existing behavior)

### Approval Workflow

#### Batch Approval Flow

**When user clicks "Approve All" or "Reject All":**
1. Collect all `requestId`s from grouped approvals
2. Optional: show feedback textarea (same feedback sent to all)
3. Send approval webhook for each `requestId` in parallel using `Promise.all`
4. Show loading state on entire card
5. On success: fade out card after 500ms, refetch approvals
6. On failure: show error details, keep card visible

**Error handling:**
- Each approval retries up to 3 times with exponential backoff
- Track succeeded vs failed approvals
- Show detailed status: "3/3 approvals sent: 2 succeeded, 1 failed (post-abc123)"
- Card remains visible showing only failed approvals for retry

#### Individual Review Flow

**When user clicks "Review Individually":**
1. Toggle card to expanded state
2. Show all approval cards below the diff viewer
3. Each approval has independent approve/reject/feedback controls
4. Can mix decisions within the group
5. Card automatically collapses when all approvals resolved

### Backend Implementation

#### Worker Agent Changes (`nd/worker/agent.py`)

**In `process_task` reasoner (where approval pause happens):**

1. Extract source metadata from task input:
   ```python
   # Task input already has: platform, platform_host, repo_owner, repo_name, mr_number (or issue_number)
   # Construct source metadata
   source_url = f"https://{platform_host}/{repo_owner}/{repo_name}/merge_requests/{mr_number}"
   source_type = "mr"  # or "issue" if from issue
   source_identifier = f"{platform}:{repo_owner}/{repo_name}#{mr_number}"
   ```

2. Include in `app.pause()` call:
   ```python
   await app.pause(
       approval_request_id=request_id,
       approval_request_url=source_url,
       expires_in_hours=72,
       # Additional custom data:
       source_url=source_url,
       source_type=source_type,
       source_identifier=source_identifier,
   )
   ```

**Handling both MRs and issues:**
- For MR comments: use `mr_url` from task metadata
- For issues: construct URL from `issue_url` in task metadata
- Source type: "mr" for comments, "issue" for assigned issues

### Frontend Implementation

#### Parser Updates (`approval-dashboard/src/utils/parser.ts`)

**In `parseApprovalContext` function:**

1. **Primary: Extract from pause context (new executions):**
   ```typescript
   const sourceUrl = data.source_url;
   const sourceType = data.source_type || 'mr';
   const sourceIdentifier = data.source_identifier;
   ```

2. **Fallback: Parse from existing fields (old executions):**
   ```typescript
   if (!sourceIdentifier) {
     // Parse from approval_request_url or task metadata
     const url = data.approval_request_url || '';
     sourceIdentifier = deriveSourceIdentifier(url, input.project);
   }
   ```

3. **Normalize different platform formats:**
   - GitHub: `github.com/owner/repo/pull/123` or `github.com/owner/repo/issues/123`
   - GitLab: `gitlab.com/owner/repo/-/merge_requests/123` or `gitlab.com/owner/repo/-/issues/123`

#### Grouping Logic (`approval-dashboard/src/utils/grouping.ts`)

**New file with grouping utility:**

```typescript
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
    if (new Date(approval.expiresAt) > group.latestTimestamp) {
      group.latestTimestamp = new Date(approval.expiresAt);
    }
  }

  // Sort groups by most recent activity
  return Array.from(groups.values()).sort(
    (a, b) => b.latestTimestamp.getTime() - a.latestTimestamp.getTime()
  );
}
```

#### Diff Aggregation (`approval-dashboard/src/utils/diff-aggregator.ts`)

**New file for combining diffs:**

```typescript
export interface DiffTab {
  label: string;
  diff: string;
  executionId: string;
  reasoner: string;
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
    // Extract diff from approval context based on type:
    // - spec: Not applicable (no code changes yet)
    // - roborev: approval.roborev?.diff (from execute_changes output)
    // - post: approval.response?.filesChanged (from execute_changes output)
    // Note: Diffs come from ExecutionResult.diff field in nd/schemas.py
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
  const MAX_LINES = 10000;
  const lines = combined.split('\n');
  const truncated = lines.length > MAX_LINES
    ? lines.slice(0, MAX_LINES).join('\n') + '\n\n# ... (truncated)'
    : combined;

  return { combined: truncated, tabs };
}

// Helper functions (to be implemented):
function extractDiffFromApproval(approval: ApprovalContext): string | null {
  // Returns diff based on approval type
  if (approval.roborev?.diff) return approval.roborev.diff;
  // Note: spec approvals don't have diffs yet (no code changes at spec stage)
  // Response approvals need diff from execute_changes - already in ResponseContext
  return null;
}

function getReasonerName(approval: ApprovalContext): string {
  // Maps approval type to reasoner that produced the code changes
  const reasonerMap = {
    spec: 'plan_changes',
    roborev: 'execute_changes',
    post: 'execute_changes'
  };
  return reasonerMap[approval.approvalType] || 'unknown';
}
```

#### Hooks

**`useGroupedApprovals.ts` (new):**
```typescript
export function useGroupedApprovals() {
  const { data: approvals, ...rest } = useApprovals();

  const grouped = useMemo(() => {
    if (!approvals) return [];
    return groupApprovalsBySource(approvals);
  }, [approvals]);

  return { data: grouped, ...rest };
}
```

**`useGroupedApprovalSubmit.ts` (new):**
```typescript
interface BatchApprovalRequest {
  requestIds: string[];
  decision: ApprovalDecision;
  feedback?: string;
}

export function useGroupedApprovalSubmit() {
  return useMutation({
    mutationFn: async (req: BatchApprovalRequest) => {
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
      queryClient.invalidateQueries(['approvals']);
    },
  });
}
```

### Testing Strategy

#### Backend Tests (`tests/unit/test_worker_agent.py`)

**Add tests for source metadata extraction:**
```python
def test_process_task_includes_source_metadata_for_mr():
    # Given a task from an MR comment
    task = create_mr_comment_task(mr_number=123)

    # When process_task creates approval pause
    result = await agent.process_task(**task)

    # Then pause context includes source metadata
    assert pause_context.source_url == "https://gitlab.com/owner/repo/-/merge_requests/123"
    assert pause_context.source_type == "mr"
    assert pause_context.source_identifier == "gitlab:owner/repo#123"

def test_process_task_includes_source_metadata_for_issue():
    # Given a task from an assigned issue
    task = create_issue_task(issue_number=456)

    # When process_task creates approval pause
    result = await agent.process_task(**task)

    # Then pause context includes source metadata
    assert pause_context.source_url == "https://github.com/owner/repo/issues/456"
    assert pause_context.source_type == "issue"
    assert pause_context.source_identifier == "github:owner/repo#456"
```

#### Frontend Tests (`approval-dashboard/src/utils/*.test.ts`)

**Test grouping logic:**
```typescript
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
  });
});
```

**Test diff aggregation:**
```typescript
describe('aggregateDiffs', () => {
  it('combines diffs with separators', () => {
    const approvals = [
      createApprovalWithDiff({ approvalType: 'spec', diff: 'diff1' }),
      createApprovalWithDiff({ approvalType: 'post', diff: 'diff2' }),
    ];

    const { combined, tabs } = aggregateDiffs(approvals);

    expect(combined).toContain('# --- Changes from spec ---');
    expect(combined).toContain('diff1');
    expect(combined).toContain('# --- Changes from post ---');
    expect(combined).toContain('diff2');
    expect(tabs).toHaveLength(2);
  });

  it('truncates combined diff at 10000 lines', () => {
    const hugeDiff = 'line\n'.repeat(15000);
    const approvals = [createApprovalWithDiff({ diff: hugeDiff })];

    const { combined } = aggregateDiffs(approvals);

    expect(combined.split('\n').length).toBeLessThanOrEqual(10001); // 10000 + truncation message
    expect(combined).toContain('(truncated)');
  });
});
```

#### E2E Tests (`approval-dashboard/tests/e2e/grouped-approval.spec.ts`)

**New E2E test file:**
```typescript
test('groups approvals by MR and shows combined diff', async ({ page }) => {
  // Setup: Create multiple approvals from same MR
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'spec' });
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'post' });

  await page.goto('http://localhost:3000');
  await page.click('text=By Source');

  // Should show one grouped card
  const cards = page.locator('[data-testid="grouped-approval-card"]');
  await expect(cards).toHaveCount(1);

  // Should show approval counts
  await expect(page.locator('text=2 approvals')).toBeVisible();
  await expect(page.locator('text=Spec: 1')).toBeVisible();
  await expect(page.locator('text=Post: 1')).toBeVisible();

  // Should show combined diff by default
  await expect(page.locator('text=Combined')).toHaveClass(/active/);
  await expect(page.locator('text=# --- Changes from spec ---')).toBeVisible();
});

test('batch approve sends all approvals and removes card', async ({ page }) => {
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'spec' });
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'post' });

  await page.goto('http://localhost:3000');
  await page.click('text=By Source');

  // Click approve all
  await page.click('[data-testid="approve-all-button"]');

  // Should send both approvals
  await expect(page.locator('[data-testid="grouped-approval-card"]')).toHaveCount(0);

  // Verify webhooks sent
  expect(mockApprovalWebhook).toHaveBeenCalledTimes(2);
});

test('individual review mode allows mixed decisions', async ({ page }) => {
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'spec' });
  await createApproval({ sourceIdentifier: 'gitlab:test/repo#123', type: 'post' });

  await page.goto('http://localhost:3000');
  await page.click('text=By Source');
  await page.click('text=Review Individually');

  // Should expand to show individual approvals
  const approvalCards = page.locator('[data-testid="approval-card"]');
  await expect(approvalCards).toHaveCount(2);

  // Approve first, reject second
  await approvalCards.nth(0).locator('button:has-text("Approve")').click();
  await approvalCards.nth(1).locator('button:has-text("Reject")').click();

  // Should send mixed decisions
  expect(mockApprovalWebhook).toHaveBeenCalledWith(
    expect.objectContaining({ decision: 'approved' })
  );
  expect(mockApprovalWebhook).toHaveBeenCalledWith(
    expect.objectContaining({ decision: 'rejected' })
  );
});
```

### Migration & Backward Compatibility

#### Phase 1: Backend Changes (Worker Agent)

**Timeline:** Immediate
**Changes:**
- Add source metadata extraction to `nd/worker/agent.py`
- New executions include `source_url`, `source_type`, `source_identifier` in pause context
- Old executions: No change, continue working

**Validation:**
- Unit tests verify metadata is included
- Manual test: trigger worker, check AgentField execution details for source fields

#### Phase 2: Frontend Changes (Dashboard)

**Timeline:** After backend deployed
**Changes:**
- Add parser logic with fallback for old executions
- Add grouping utilities and components
- Add "By Source" tab

**Backward compatibility:**
- Parser checks for source metadata first
- Falls back to deriving from `mrUrl` or task body if missing
- Approvals without parseable source: show in "Ungrouped" section at bottom of "By Source" tab

**Validation:**
- Unit tests cover fallback parsing
- E2E tests with mix of old/new executions
- Manual test: verify old approvals still work

#### Phase 3: Cleanup (Optional, Future)

**Timeline:** After 72 hours (all old executions expired)
**Changes:**
- Remove fallback parsing logic (source metadata now required)
- Remove "Ungrouped" section handling

### File Changes Summary

#### Backend Files

**Modified:**
- `nd/schemas.py` - Add `source_url`, `source_type`, `source_identifier` fields
- `nd/worker/agent.py` - Extract and include source metadata in `app.pause()` calls
- `tests/unit/test_worker_agent.py` - Add source metadata tests

#### Frontend Files

**Modified:**
- `src/api/types.ts` - Add `GroupedApproval` interface, extend `ApprovalContext`
- `src/utils/parser.ts` - Extract source metadata with fallback logic
- `src/App.tsx` - Add "By Source" tab (first position)

**New:**
- `src/utils/grouping.ts` - Group approvals by source identifier
- `src/utils/diff-aggregator.ts` - Combine diffs chronologically
- `src/hooks/useGroupedApprovals.ts` - Hook wrapping `useApprovals()` with grouping
- `src/hooks/useGroupedApprovalSubmit.ts` - Batch approval mutation hook
- `src/components/GroupedApprovalList.tsx` - List container for grouped cards
- `src/components/GroupedApprovalCard.tsx` - Card showing MR/issue with approvals
- `src/components/TabbedDiffViewer.tsx` - Tabbed diff viewer with combined view
- `tests/e2e/grouped-approval.spec.ts` - E2E tests for grouping workflow

### Implementation Order

1. **Backend: Add source metadata** (`nd/worker/agent.py`, `nd/schemas.py`)
   - Extract source info from task metadata
   - Include in `app.pause()` call
   - Add unit tests

2. **Frontend: Type system** (`src/api/types.ts`)
   - Add `sourceUrl`, `sourceType`, `sourceIdentifier` to `ApprovalContext`
   - Add `GroupedApproval` interface

3. **Frontend: Parser & utilities** (`src/utils/`)
   - Update parser to extract source metadata with fallback
   - Add `grouping.ts` with grouping logic
   - Add `diff-aggregator.ts` with diff combining logic
   - Add unit tests

4. **Frontend: Hooks** (`src/hooks/`)
   - Add `useGroupedApprovals.ts`
   - Add `useGroupedApprovalSubmit.ts`

5. **Frontend: Components** (bottom-up)
   - Add `TabbedDiffViewer.tsx`
   - Add `GroupedApprovalCard.tsx`
   - Add `GroupedApprovalList.tsx`

6. **Frontend: Integration** (`src/App.tsx`)
   - Add "By Source" tab
   - Wire up `GroupedApprovalList` component
   - Handle empty state

7. **Testing: E2E** (`tests/e2e/`)
   - Add grouped approval workflow tests
   - Validate batch approval
   - Validate individual review mode

8. **Documentation & commit**
   - Update README with "By Source" tab documentation
   - Commit all changes

### Success Criteria

✅ Worker agent includes source metadata in all new approval pause contexts
✅ Dashboard "By Source" tab groups approvals by MR/issue
✅ Combined diff tab shows all changes from grouped approvals with separators
✅ Individual diff tabs show each execution's changes
✅ "Approve All" / "Reject All" buttons send batch approvals and remove card on success
✅ "Review Individually" toggle expands to show individual approval cards
✅ Individual review mode allows mixed decisions (approve some, reject others)
✅ Old executions without source metadata gracefully degrade (fallback parsing or ungrouped)
✅ All existing unit and E2E tests pass
✅ New E2E tests cover grouping workflow, batch approval, and individual review
✅ No breaking changes to existing approval tabs (Spec Reviews, Roborev Failures, Response Approvals)

## Risks & Mitigations

### Risk 1: Source identifier collision between platforms

**Risk:** Two platforms might use the same `owner/repo#number` format (e.g., GitHub and GitLab)

**Mitigation:** Include platform prefix in identifier: `gitlab:owner/repo#123` vs `github:owner/repo#123`

### Risk 2: Mixed old/new approvals from same MR

**Risk:** An MR has some approvals with source metadata and some without (during transition period)

**Mitigation:**
- Parser fallback ensures old approvals get correct source identifier from `mrUrl`
- Grouping works regardless of metadata source
- All approvals from same MR end up in same group

### Risk 3: Diff aggregation performance with large changes

**Risk:** Combining many large diffs could slow down rendering

**Mitigation:**
- Lazy load diffs only when tab is clicked
- Truncate combined diff at 10,000 lines
- Individual diff tabs have no size limit (existing behavior)
- Use `useMemo` to avoid re-computing on every render

### Risk 4: Partial batch approval failures

**Risk:** Some approvals in a batch succeed, others fail (network issues, webhook timeout)

**Mitigation:**
- Track succeeded vs failed approvals individually
- Show detailed error message: "3/3 approvals sent: 2 succeeded, 1 failed"
- Keep card visible with only failed approvals
- Allow retry of failed approvals

### Risk 5: Task metadata missing source information

**Risk:** Triage agent doesn't include MR/issue URL in some edge cases

**Mitigation:**
- Worker agent logs warning if source info missing
- Falls back to "unknown" source type
- Dashboard shows in "Ungrouped" section
- Doesn't break approval workflow

## Future Enhancements

### Spec Feedback Mechanism (Next Feature)

Add ability to request more information for specs that need clarification:
- "Request Changes" button on spec reviews
- Feedback form with common request templates
- Send feedback via approval webhook with `decision: "request_changes"`
- Worker agent adds feedback to kata task comment and re-pauses

### Historical Approval Analytics

Track approval patterns by source:
- Average time to approve per MR/issue
- Approval/reject rates by project
- Most common approval types (spec vs roborev vs response)

### AgentField Grouped Queries

Add API endpoint to fetch approvals pre-grouped by source:
- `GET /api/v1/runs/grouped?status=waiting`
- Returns grouped structure directly
- Eliminates frontend grouping logic

## Questions & Decisions

### Q: Should "By Source" be the default tab?

**Decision:** Yes, make it the first (leftmost) tab since it's the primary grouping view that most engineers will want.

### Q: How to handle approvals without a parseable source?

**Decision:** Show in "Ungrouped" section at bottom of "By Source" tab with warning badge.

### Q: Should batch approval require confirmation?

**Decision:** No, keep it fast. Users can use "Review Individually" if they want to confirm each one.

### Q: How to handle very large combined diffs?

**Decision:** Truncate at 10,000 lines with warning message. Individual tabs have no limit.

### Q: Should we support partial batch approval (approve some, skip others)?

**Decision:** No, keep it simple: batch approve/reject all, or use individual review mode for mixed decisions.
