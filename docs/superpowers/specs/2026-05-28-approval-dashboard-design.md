# AgentField Approval Dashboard Design

**Date:** 2026-05-28
**Status:** Approved

## Summary

A single-page React application that displays paused AgentField executions with comprehensive context, allowing human reviewers to approve or reject them directly from a web interface. The dashboard polls AgentField's API to discover waiting executions and sends approval webhooks with HMAC signatures.

## Problem Statement

The nd worker agent has three human approval gates (spec review, roborev failure, response approval) that currently require manual intervention via command-line scripts. There's no unified UI to:

1. Discover which executions are waiting for approval
2. View the full context needed to make approval decisions
3. Approve/reject with a single click and optional feedback
4. Track approval history and execution traces

The current workflow requires:
- Checking AgentField UI at `http://localhost:8081/ui/runs/`
- Grepping docker logs for approval request IDs
- Running `./scripts/approve.py <id> <decision>` manually
- No visibility into what each approval is actually about

## Requirements

### Functional Requirements

1. **Discovery**: Automatically poll AgentField for paused executions (status=waiting)
2. **Context Display**: Show comprehensive information for each approval type:
   - Spec Reviews: original comment, confidence score, generated spec, risks, questions
   - Roborev Failures: files changed, commit SHA, roborev findings
   - Response Approvals: draft response (editable), files changed, commit SHA, MR/PR link
3. **Approval Actions**: Support approve/reject/request_changes with optional feedback
4. **Real-time Updates**: Auto-refresh every 5 seconds, optimistic UI updates
5. **Execution History**: View full AgentField execution trace for debugging

### Non-Functional Requirements

1. **Performance**: Dashboard loads in <2s, polling doesn't block UI
2. **Security**: HMAC signatures required (hardcoded dev secret acceptable)
3. **Usability**: Clear visual hierarchy, mobile-responsive layout
4. **Reliability**: Graceful degradation when AgentField unavailable

### Out of Scope

- Multi-user authentication/authorization (single-user dev tool)
- Production-grade secret management (hardcoded dev secret is fine)
- Historical approval logs (AgentField owns this data)
- Custom polling intervals or AgentField URL configuration

## Proposed Solution

### Architecture

**Frontend Stack:**
- React 18+ with TypeScript for type safety
- Vite for fast dev server and minimal config
- TanStack Query (React Query) for API state management and polling
- Tailwind CSS for rapid styling
- Lucide React for consistent iconography

**Data Flow:**
```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (SPA)                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  React Dashboard                                      │  │
│  │  - Polls /api/v1/runs?status=waiting every 5s       │  │
│  │  - Fetches /api/v1/runs/{runId} for details         │  │
│  │  - Generates HMAC signatures client-side             │  │
│  └─────────────┬────────────────────────────────────────┘  │
│                │                                             │
│                ├─────── GET /api/v1/runs ────────────────┐  │
│                │                                          │  │
│                └─ POST /api/v1/webhooks/approval-response  │
│                   (with X-Hub-Signature-256 header)      │  │
└────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   AgentField        │
                    │   localhost:8081    │
                    └─────────────────────┘
```

### Component Hierarchy

```
App
├── Header (connection status, title)
├── Tabs (Spec Reviews | Roborev Failures | Response Approvals)
└── ApprovalList
    └── ApprovalCard (per execution)
        ├── CardHeader (type badge, task ID, timing)
        ├── ContextSection (approval-type-specific)
        │   ├── SpecReviewContext
        │   ├── RoborevContext
        │   └── ResponseContext
        ├── ExecutionHistory (expandable trace)
        └── ActionButtons (approve/reject/feedback)
```

### Data Model

**AgentField Run (from API):**
```typescript
interface AgentFieldRun {
  runId: string;
  nodeId: string;
  status: 'waiting' | 'running' | 'completed' | 'failed';
  createdAt: string;
  updatedAt: string;
  trace: ReasonerCall[];
  pauseContext?: {
    approval_request_id: string;
    approval_request_url: string;
    expires_in_hours: number;
    timeout: number;
  };
}

interface ReasonerCall {
  name: string;
  input: Record<string, any>;
  output: Record<string, any>;
  timestamp: string;
  duration_ms: number;
}
```

**Parsed Approval Context:**
```typescript
interface ApprovalContext {
  approvalType: 'spec' | 'roborev' | 'post';
  taskId: string;
  runId: string;
  requestId: string; // e.g., "spec-537b"
  mrUrl?: string;
  expiresAt: Date;

  // Extracted from execution trace
  originalComment: string;
  taskTitle: string;
  projectName: string;

  // Type-specific context
  spec?: SpecReviewContext;
  roborev?: RoborevContext;
  response?: ResponseContext;
}

interface SpecReviewContext {
  confidence: number;
  complexity: 1 | 2 | 3 | 4 | 5;
  reasoning: string;
  suggestedApproach: string;
  filesLikelyAffected: string[];
  spec: {
    summary: string;
    problemStatement: string;
    proposedSolution: string;
    filesToModify: string[];
    filesToCreate: string[];
    testingApproach: string;
    risks: string[];
    questions: string[];
  };
}

interface RoborevContext {
  filesChanged: string[];
  commitSha: string;
  iterations: number;
  findings: string[];
  originalComment: string;
}

interface ResponseContext {
  draftResponse: string;
  filesChanged: string[];
  commitSha: string;
  originalComment: string;
  mrUrl: string;
}
```

### API Integration

**1. Poll for Waiting Executions**
```typescript
// Every 5 seconds
GET http://localhost:8081/api/v1/runs?status=waiting

// Filter to only nd-worker runs
runs.filter(r => r.nodeId === 'nd-worker')
```

**2. Fetch Execution Details**
```typescript
GET http://localhost:8081/api/v1/runs/{runId}

// Parse trace to extract context:
// - process_task input → task_id, project, title, body
// - analyze_task output → confidence, complexity, reasoning
// - plan_changes output → spec document
// - execute_changes output → files_changed, commit_sha
// - run_roborev output → passed, findings
// - draft_response output → response_text
```

**3. Send Approval**
```typescript
POST http://localhost:8081/api/v1/webhooks/approval-response
Headers:
  Content-Type: application/json
  X-Hub-Signature-256: sha256={hmac_hex}
Body:
{
  "requestId": "post-537b",
  "decision": "approved" | "rejected" | "request_changes",
  "feedback": "optional human feedback"
}

// HMAC signature computed with Web Crypto API:
const signature = await hmacSha256("nd-approval-secret-dev", jsonBody);
```

### UI Components

#### Dashboard View
- **Header**: "AgentField Approvals" with connection status dot (green/yellow/red)
- **Tabs**: Three tabs with count badges showing pending approvals per type
- **Auto-refresh**: Poll every 5s, show "Updated 3s ago" indicator
- **Empty state**: "No pending approvals" with party emoji when all clear

#### Approval Card
**Header Section:**
- Type badge (blue for spec, orange for roborev, green for response)
- Task ID as link to MR/PR
- Waiting duration (e.g., "Waiting 5m")
- Expiration countdown (e.g., "Expires in 71h")

**Context Section (varies by type):**

*Spec Review Card:*
- Collapsible "Original Comment" section
- Confidence score with color-coded badge (red <70, yellow 70-85, green >85)
- Complexity indicator (1-5 stars)
- "Suggested Approach" callout box
- Spec document with sections: Summary, Problem, Solution, Files, Risks, Questions
- Files likely affected (clickable chips)

*Roborev Failure Card:*
- Files changed list with diff line counts
- Commit SHA (copy button)
- Roborev findings (max 10, syntax-highlighted)
- Iterations attempted indicator
- Link to "View in repo" button

*Response Approval Card:*
- **Editable** draft response textarea
- Files changed summary
- Commit SHA with link
- Original comment (collapsed by default)
- "Preview in MR" button

**Execution History (Expandable):**
- Accordion showing full execution trace
- Each reasoner call with timing, inputs (collapsed), outputs (collapsed)
- Syntax-highlighted JSON viewer

**Action Section:**
- Large "Approve" button (primary green)
- "Reject" button (secondary red)
- "Request Changes" button (for responses only)
- Feedback textarea (expands on first click)
- Submit disabled during pending request

#### UI States

1. **Loading**: Skeleton cards with pulse animation
2. **Empty**: Center-aligned message "No pending approvals"
3. **Error**: Banner at top "Connection lost. Retrying..." with manual refresh
4. **Submitting**: Disabled buttons, spinner on active button
5. **Success**: Toast notification "Approval sent", card fades out after 500ms
6. **Stale Data**: Yellow indicator if last poll >10s ago

### File Structure

```
approval-dashboard/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── index.html
└── src/
    ├── main.tsx                    # App entry point + React Query setup
    ├── App.tsx                     # Root with tabs and polling logic
    ├── api/
    │   ├── agentfield.ts           # API client (fetch wrappers)
    │   ├── hmac.ts                 # HMAC-SHA256 signature generation
    │   └── types.ts                # TypeScript interfaces
    ├── components/
    │   ├── ApprovalCard.tsx        # Base card with common layout
    │   ├── SpecReviewCard.tsx      # Spec-specific rendering
    │   ├── RoborevCard.tsx         # Roborev-specific rendering
    │   ├── ResponseCard.tsx        # Response-specific with editable text
    │   ├── ExecutionHistory.tsx    # Collapsible trace viewer
    │   ├── ConnectionStatus.tsx    # Health indicator dot + text
    │   └── ApprovalActions.tsx     # Approve/reject/feedback buttons
    ├── hooks/
    │   ├── useApprovals.ts         # React Query hook for polling
    │   └── useApprovalSubmit.ts    # Mutation hook for sending approvals
    └── utils/
        ├── parser.ts               # Parse execution trace → ApprovalContext
        └── formatting.ts           # Date/time formatting helpers
```

### Configuration

**Hardcoded Constants:**
```typescript
// src/api/agentfield.ts
export const AGENTFIELD_URL = 'http://localhost:8081';
export const WEBHOOK_SECRET = 'nd-approval-secret-dev';
export const POLL_INTERVAL_MS = 5000;
export const REQUEST_TIMEOUT_MS = 10000;
```

### Error Handling

**Network Errors:**
- Show reconnecting banner at top of dashboard
- Exponential backoff: 5s → 10s → 20s → 40s (max)
- Manual "Retry Now" button in banner

**Invalid Responses:**
- Log to console with full error context
- Show generic error message to user
- Don't crash, keep polling

**Missing Data:**
- Gracefully degrade (show what we have)
- Display "Context unavailable" placeholder for missing sections
- Still allow approval/rejection (with warning)

**AgentField Down:**
- Red connection indicator
- "AgentField Unavailable" full-page state
- Retry button

### Testing Approach

**Manual Testing:**
1. Start nd worker, trigger low-confidence task → verify spec review appears
2. Approve via dashboard → verify worker resumes and executes
3. Trigger roborev failure → verify findings displayed correctly
4. Approve response → verify MR comment posted
5. Reject at each gate → verify worker labels task "needs-human"

**Mock Data Mode:**
- Add `?mock=true` query param to load fake paused executions
- Allows UI development without running full nd stack

**Browser Testing:**
- Chrome/Firefox/Safari compatibility
- Mobile responsive (min width 375px)

## Risks

1. **AgentField API changes**: Dashboard tightly coupled to AgentField's run structure
   - *Mitigation*: Version API calls, graceful degradation for missing fields

2. **HMAC signature mismatch**: Client-side crypto subtle API not available in insecure contexts
   - *Mitigation*: Serve dashboard over localhost (secure context), fallback to TextEncoder+SubtleCrypto

3. **Polling overhead**: Frequent API calls could impact AgentField performance
   - *Mitigation*: 5s interval is reasonable, use conditional requests (ETag) if available

4. **Task context missing**: Kata task body not accessible from browser
   - *Mitigation*: Extract all context from AgentField execution trace (already contains task body in process_task input)

5. **Stale approvals**: User approves execution that already timed out
   - *Mitigation*: Show expiration countdown, disable actions if expired

## Questions

1. Should we add keyboard shortcuts (e.g., `a` for approve, `r` for reject)?
2. Do we need dark mode support?
3. Should approval history be persisted (localStorage)?
4. Do we want browser notifications when new approvals arrive?

## Success Criteria

1. Dashboard loads and displays all three types of paused executions
2. Clicking "Approve" resumes the worker and completes the task
3. Clicking "Reject" causes worker to label task "needs-human"
4. Edited response text is sent as feedback and posted to MR
5. UI updates in <500ms after approval action
6. No console errors during normal operation

## Implementation Plan

See `docs/superpowers/plans/2026-05-28-approval-dashboard-plan.md`
