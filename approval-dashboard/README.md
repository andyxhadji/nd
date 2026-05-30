# AgentField Approval Dashboard

Web UI for reviewing and approving paused AgentField executions from nd agents.

## Quick Start

```bash
npm install
npm run dev
```

Open http://localhost:3000

## Requirements

- Node.js 18+
- AgentField running at http://localhost:8081
- nd worker with paused executions

## Features

- **Auto-refresh**: Polls AgentField every 5 seconds
- **Three approval types**: Spec reviews, roborev failures, response approvals
- **Grouped by source**: View all approvals from the same MR/Issue together with combined diffs
- **Batch approval**: Approve or reject all changes from a source at once
- **Comprehensive context**: Shows all info needed to make decisions
- **HMAC signatures**: Secure approval webhooks
- **Execution history**: View full AgentField trace for debugging

## Development

```bash
npm run dev        # Start dev server
npm run build      # Build for production
npm run preview    # Preview production build
npm test           # Run unit tests
npm run test:e2e   # Run E2E tests
```

## UI Tabs

### By Source (Default)
Groups all approvals from the same MR or Issue together, showing:
- Combined diff across all approval types
- Source metadata (MR/Issue number, title, URL)
- Batch approval buttons (approve/reject all)
- Individual approval cards with expandable diffs

### Agent Control
Manual triggers for:
- Triage agent: poll_issues, poll_comments
- Worker agent: claim_task

### Spec Reviews / Roborev Failures / Response Approvals
Individual approval cards filtered by type (legacy view)

## Testing

### Manual Test: Spec Review

1. Start nd worker
2. Trigger a low-confidence task (confidence < 70)
3. Worker pauses at spec review gate
4. Dashboard shows spec review card
5. Click "Approve"
6. Worker resumes and executes

### Manual Test: Roborev Failure

1. Start nd worker
2. Trigger a task that produces code with issues
3. Worker runs roborev, fails after max iterations
4. Dashboard shows roborev failure card
5. Click "Reject" with feedback
6. Worker labels task "needs-human"

### Manual Test: Response Approval

1. Start nd worker
2. Trigger any task
3. Worker completes execution and pauses at response gate
4. Dashboard shows response approval card with draft
5. Edit draft response text
6. Click "Approve"
7. Worker posts edited response to MR

## Architecture

- **Frontend**: React 18 + TypeScript + Vite
- **State Management**: TanStack Query (React Query)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

## Configuration

Hardcoded in `src/api/agentfield.ts`:
- `AGENTFIELD_URL`: http://localhost:8081
- `WEBHOOK_SECRET`: nd-approval-secret-dev
- `POLL_INTERVAL_MS`: 5000 (5 seconds)
