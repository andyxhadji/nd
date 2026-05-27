# nd AgentField Architecture

Design spec for rebuilding nd as a set of autonomous AgentField agents.

## Overview

nd currently exists as a Claude Code plugin with three declarative skills (triage, address, post-comments). This design rebuilds it as a set of AgentField agents that run as autonomous daemons, integrating with middleman (PR/MR sync), kata (task tracking), and roborev (code review).

### Goals

1. **Fully autonomous operation** - Agents run continuously without human invocation
2. **Scalable worker pool** - Multiple worker instances can process tasks concurrently
3. **Confidence-gated human approval** - Complex specs and all response postings require human review via AgentField's pause mechanism
4. **Post-hoc audit trail** - All completed work is reviewable after the fact

### Non-Goals

- Real-time webhook triggers from middleman (using cron polling instead)
- Automatic response posting without human review (future enhancement)
- Cross-MR coordination or conflict resolution (workers claim independent tasks)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AgentField Control Plane                           │
│                    (orchestration, workflow DAG, pause UI)                  │
└─────────────────────────────────────────────────────────────────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ triage-agent  │         │  worker-agent   │         │  worker-agent   │
│  (cron loop)  │         │   (instance 1)  │         │   (instance N)  │
└───────┬───────┘         └────────┬────────┘         └────────┬────────┘
        │                          │                           │
        ▼                          ▼                           ▼
┌───────────────┐         ┌─────────────────────────────────────────────────┐
│   Middleman   │◄────────│                     Kata                        │
│  (PR/MR sync) │         │              (task tracking)                    │
└───────────────┘         └─────────────────────────────────────────────────┘
                                           │
                                           ▼
                                   ┌───────────────┐
                                   │    Roborev    │
                                   │ (code review) │
                                   └───────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **AgentField Control Plane** | Orchestration, workflow DAG tracking, pause/resume UI, verifiable credentials |
| **Triage Agent** | Poll middleman for new MR comments, create kata tasks for actionable items |
| **Worker Agent(s)** | Claim tasks from kata, analyze, make code changes, run roborev, draft responses |
| **Middleman** | Sync PR/MR data from GitHub/GitLab to local SQLite, provide REST API |
| **Kata** | Track tasks with labels, comments, events; provide claiming mechanism |
| **Roborev** | Review code changes, iterate on fixes, validate quality |

## Agent 1: Triage Agent

### Purpose

Poll middleman for new MR comments since last run, classify each as actionable or not, and create kata tasks for actionable items.

### Configuration

```python
app = Agent(
    node_id="nd-triage",
    version="1.0.0",
    agentfield_server=os.getenv("AGENTFIELD_URL", "http://localhost:8080"),
    ai_config=AIConfig(
        model=os.getenv("TRIAGE_MODEL", "openrouter/anthropic/claude-sonnet-4"),
        temperature=0.3,
    ),
)
```

### Reasoners

#### `poll_comments` (entry, cron-triggered)

**Trigger:** `@on_schedule("*/5 * * * *")` - every 5 minutes

**Responsibility:** Query middleman for comments since last poll, fan out to classification.

**Inputs:**
- None (reads last_poll_timestamp from app.memory)

**Outputs:**
```python
class PollResult(BaseModel):
    comments_found: int
    tasks_created: int
    skipped: int
    errors: list[str]
```

**Flow:**
1. Read `last_poll_timestamp` from `app.memory` (scope: agent)
2. Query middleman API: `GET /api/v1/activity?types=issue_comment&since={timestamp}`
3. Filter to comments on MRs where current user is author
4. For each comment, call `classify_actionable` in parallel via `asyncio.gather`
5. For actionable comments, call `create_task`
6. Update `last_poll_timestamp` in memory
7. Return summary

**Middleman Query:**
```sql
SELECT
    e.id, e.body, e.author, e.created_at, e.dedupe_key, e.platform_external_id,
    mr.number, mr.title, mr.head_branch, mr.base_branch, mr.url,
    r.platform, r.platform_host, r.owner, r.name
FROM middleman_mr_events e
JOIN middleman_merge_requests mr ON e.merge_request_id = mr.id
JOIN middleman_repos r ON mr.repo_id = r.id
WHERE e.event_type = 'issue_comment'
  AND mr.state = 'open'
  AND mr.author = :current_user
  AND e.created_at > :last_poll_timestamp
ORDER BY e.created_at ASC
```

#### `classify_actionable`

**Responsibility:** Determine if a comment requires action.

**Inputs:**
```python
class CommentInput(BaseModel):
    body: str
    author: str
    mr_title: str
    mr_number: int
```

**Outputs:**
```python
class ClassificationResult(BaseModel):
    actionable: bool
    reason: str
    category: Literal["question", "request", "feedback", "acknowledgment", "bot", "other"]
    confident: bool
```

**Logic:**
1. Skip if author is a known bot (dependabot, renovate, etc.)
2. Skip if body matches non-actionable patterns (LGTM, thanks, +1, etc.)
3. Use LLM to classify ambiguous cases
4. Return actionable=True for: questions, explicit requests, review feedback
5. Return actionable=False for: acknowledgments, bot comments, off-topic

**Actionable Patterns (deterministic, checked first):**
- Contains `?` and is directed at author
- Contains: "please", "can you", "could you", "fix", "change", "update", "add", "remove"
- Starts with: "nit:", "suggestion:", "todo:", "blocking:"

**Non-Actionable Patterns (deterministic, checked first):**
- Exact match: "LGTM", "looks good", "approved", "+1", "thanks", "thank you"
- Author is bot (ends with `[bot]` or in known bot list)

#### `create_task`

**Responsibility:** Create a kata task with rich metadata.

**Inputs:**
```python
class TaskInput(BaseModel):
    comment_body: str
    comment_author: str
    comment_dedupe_key: str
    mr_number: int
    mr_title: str
    mr_url: str
    head_branch: str
    base_branch: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    classification: ClassificationResult
```

**Outputs:**
```python
class TaskCreationResult(BaseModel):
    created: bool
    task_id: str | None
    skipped_reason: str | None
```

**Flow:**
1. Check for existing task with same dedupe_key: `kata search --project {repo_name} "{dedupe_key}"`
2. If exists, return `created=False, skipped_reason="duplicate"`
3. Generate task title (first sentence of comment or truncated to 80 chars)
4. Create task body with structured metadata:
   ```markdown
   ## MR Context
   - **MR:** [{repo_owner}/{repo_name}!{mr_number}]({mr_url})
   - **Title:** {mr_title}
   - **Branch:** {head_branch} -> {base_branch}
   - **Platform:** {platform} ({platform_host})

   ## Original Comment
   **Author:** {comment_author}

   {comment_body}

   ## Metadata
   - **Dedupe Key:** `{dedupe_key}`
   - **Category:** {classification.category}
   ```
5. Create task: `kata create "{title}" --body "{body}" --project {repo_name} --label from-mr --label nd --idempotency-key "{dedupe_key}"`
6. Return task_id

### State Management

| Key | Scope | Purpose |
|-----|-------|---------|
| `last_poll_timestamp` | agent | ISO timestamp of last successful poll |
| `known_bots` | global | List of bot usernames to skip |

### Error Handling

- Middleman API unavailable: Log error, retry next poll cycle
- Kata API unavailable: Log error, skip task creation, retry next cycle
- LLM classification fails: Default to `actionable=True` (err on side of creating tasks)

## Agent 2: Worker Agent

### Purpose

Claim tasks from kata, analyze complexity, make code changes, run roborev, draft and post responses.

### Configuration

```python
app = Agent(
    node_id="nd-worker",
    version="1.0.0",
    agentfield_server=os.getenv("AGENTFIELD_URL", "http://localhost:8080"),
    ai_config=AIConfig(
        model=os.getenv("WORKER_MODEL", "openrouter/anthropic/claude-sonnet-4"),
        temperature=0.2,
    ),
)
```

**Scaling:** Run N instances with unique `AGENT_INSTANCE_ID` env var. All instances share the same `node_id` but register separately with the control plane.

### Reasoners

#### `claim_task` (entry, cron-triggered)

**Trigger:** `@on_schedule("* * * * *")` - every minute

**Responsibility:** Poll kata for unclaimed tasks, claim one, hand off to processing.

**Inputs:** None

**Outputs:**
```python
class ClaimResult(BaseModel):
    claimed: bool
    task_id: str | None
    project: str | None
```

**Flow:**
1. Query kata for available tasks: `kata ready --label nd --unowned --json`
2. If no tasks available, return `claimed=False`
3. Claim first available task: `kata assign {task_id} {worker_instance_id}`
4. Call `process_task` with task details
5. Return claim result

#### `process_task`

**Responsibility:** Orchestrate the full task processing flow.

**Inputs:**
```python
class TaskDetails(BaseModel):
    task_id: str
    project: str
    title: str
    body: str
    labels: list[str]
```

**Outputs:**
```python
class ProcessResult(BaseModel):
    status: Literal["completed", "paused_for_spec", "paused_for_review", "failed"]
    changes_made: list[str]
    response_draft: str | None
    error: str | None
```

**Flow:**
1. Parse task body to extract MR context and original comment
2. Call `analyze_task` to determine complexity/confidence
3. If confidence < threshold:
   - Call `plan_changes` to create spec
   - Call `app.pause()` for human spec review
   - On approval, continue; on rejection, mark task `needs-human` and return
4. Call `execute_changes` via `app.harness()`
5. Call `run_roborev` for quality validation
6. If roborev fails after max iterations:
   - Call `app.pause()` for human review of failure
   - On approval with guidance, retry; on rejection, mark task failed
7. Call `draft_response` to generate response text
8. Call `request_post_approval` with draft (always pauses)
9. On approval, call `post_response`
10. Call `finalize_task` to update kata

#### `analyze_task`

**Responsibility:** Assess task complexity and confidence level.

**Inputs:**
```python
class AnalysisInput(BaseModel):
    comment_body: str
    comment_category: str
    mr_title: str
    head_branch: str
    repo_path: str  # local path to repo
```

**Outputs:**
```python
class AnalysisResult(BaseModel):
    complexity: Literal[1, 2, 3, 4, 5]  # 1=trivial, 5=major
    confidence: int  # 0-100
    reasoning: str
    suggested_approach: str
    files_likely_affected: list[str]
    confident: bool
```

**Complexity Factors:**
- **1 (trivial):** Typo fix, comment update, simple rename
- **2 (minor):** Small logic change, add logging, update error message
- **3 (moderate):** New function, refactor existing code, add tests
- **4 (significant):** New feature, architectural change, multiple files
- **5 (major):** Cross-cutting concern, breaking change, needs design

**Confidence Factors:**
- Comment clarity (explicit vs ambiguous request)
- Scope clarity (specific file/line vs general area)
- Domain familiarity (based on file patterns)
- Risk level (tests exist, type safety, etc.)

**Threshold:** `CONFIDENCE_THRESHOLD` env var, default 70

#### `plan_changes`

**Responsibility:** Create a detailed spec for complex/low-confidence tasks.

**Inputs:**
```python
class PlanInput(BaseModel):
    task_id: str
    comment_body: str
    analysis: AnalysisResult
    repo_path: str
```

**Outputs:**
```python
class SpecDocument(BaseModel):
    summary: str
    problem_statement: str
    proposed_solution: str
    files_to_modify: list[str]
    files_to_create: list[str]
    testing_approach: str
    risks: list[str]
    questions: list[str]  # for human reviewer
    confident: bool
```

**Flow:**
1. Read relevant files identified in analysis
2. Use LLM to draft spec document
3. Return spec for inclusion in pause request

#### `execute_changes`

**Responsibility:** Make code changes using a coding agent harness.

**Inputs:**
```python
class ExecutionInput(BaseModel):
    task_id: str
    spec: SpecDocument | None  # None for high-confidence tasks
    comment_body: str
    repo_path: str
    head_branch: str
```

**Outputs:**
```python
class ExecutionResult(BaseModel):
    success: bool
    files_changed: list[str]
    commit_sha: str | None
    error: str | None
```

**Flow:**
1. Checkout the MR branch: `git checkout {head_branch}`
2. Invoke coding harness:
   ```python
   result = await app.harness(
       goal=f"Address this code review comment:\n\n{comment_body}\n\nSpec:\n{spec}",
       provider="claude-code",
       tools=["read", "write", "edit", "bash"],
       max_iterations=20,
   )
   ```
3. Stage and commit changes:
   ```bash
   git add -A
   git commit -m "Address review comment\n\nkata#{task_id}"
   ```
4. Return result with commit SHA

#### `run_roborev`

**Responsibility:** Run roborev-refine and handle iteration.

**Inputs:**
```python
class RoborevInput(BaseModel):
    repo_path: str
    commit_sha: str
    max_iterations: int = 3
```

**Outputs:**
```python
class RoborevResult(BaseModel):
    passed: bool
    iterations: int
    final_findings: list[str]
    error: str | None
```

**Flow:**
1. Invoke roborev refine:
   ```bash
   roborev refine --max-iterations {max_iterations} --wait
   ```
2. Parse output for pass/fail status
3. If passed, return success
4. If failed after max iterations, return with findings for human review

#### `draft_response`

**Responsibility:** Generate response text based on changes made.

**Inputs:**
```python
class DraftInput(BaseModel):
    comment_body: str
    changes_made: list[str]
    commit_sha: str
    commit_diff: str
```

**Outputs:**
```python
class DraftResult(BaseModel):
    response_text: str
    confident: bool
```

**Response Template:**
```markdown
Addressed in {commit_sha}.

{summary_of_changes}

Let me know if you'd like any adjustments.
```

#### `request_post_approval`

**Responsibility:** Pause execution for human approval of response.

**Inputs:**
```python
class ApprovalRequest(BaseModel):
    task_id: str
    mr_url: str
    original_comment: str
    response_draft: str
    commit_sha: str
    commit_diff: str
    changes_summary: list[str]
```

**Flow:**
1. Generate approval request ID
2. Call `app.pause()`:
   ```python
   result = await app.pause(
       approval_request_id=f"post-{task_id}",
       approval_request_url=f"{AGENTFIELD_UI}/approvals/{approval_request_id}",
       expires_in_hours=72,
       timeout=259200,  # 72 hours
       context={
           "type": "response_approval",
           "task_id": task_id,
           "mr_url": mr_url,
           "original_comment": original_comment,
           "response_draft": response_draft,
           "commit_sha": commit_sha,
           "commit_diff": commit_diff,
           "changes_summary": changes_summary,
       },
   )
   ```
3. Return approval result (approved/rejected/changes_requested)

**AgentField UI Context:**
The control plane UI displays paused executions with their context. The human reviewer sees:
- Original comment that triggered the task
- Draft response text (editable)
- Commit diff showing changes made
- Approve / Request Changes / Reject buttons

#### `post_response`

**Responsibility:** Post approved response to the MR.

**Inputs:**
```python
class PostInput(BaseModel):
    response_text: str
    dedupe_key: str  # to resolve original comment ID
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    mr_number: int
```

**Flow:**
1. Query middleman for comment details using dedupe_key
2. Resolve platform-specific API endpoint:
   - **GitLab:** `POST /api/v4/projects/{id}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes`
   - **GitHub:** `POST /repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies`
3. Post response as threaded reply
4. Push the commit: `git push origin {head_branch}`

#### `finalize_task`

**Responsibility:** Update kata task state after completion.

**Inputs:**
```python
class FinalizeInput(BaseModel):
    task_id: str
    status: Literal["completed", "failed", "needs-human"]
    response_posted: bool
    commit_sha: str | None
```

**Flow:**
1. Add completion comment to task:
   ```bash
   kata comment {task_id} "Response posted. Commit: {commit_sha}"
   ```
2. Add label based on outcome:
   ```bash
   kata label {task_id} responded  # or failed, needs-human
   ```
3. Close task if completed:
   ```bash
   kata close {task_id} --reason done --comment "Addressed and responded"
   ```

### Pause Points Summary

| Pause Point | Trigger | Context Shown | Actions |
|-------------|---------|---------------|---------|
| **Spec Review** | confidence < threshold | Spec document, questions | Approve / Edit / Reject |
| **Roborev Failure** | max iterations exceeded | Findings, diff | Approve (with guidance) / Reject |
| **Response Approval** | always (for now) | Comment, response, diff | Approve / Edit / Reject |

### State Management

| Key | Scope | Purpose |
|-----|-------|---------|
| `in_progress_task` | workflow | Currently claimed task ID |
| `confidence_threshold` | agent | Threshold for auto-processing (default 70) |

### Error Handling

- **Kata claim race:** Another worker claimed first - return `claimed=False`, try again next cycle
- **Git checkout fails:** Branch doesn't exist or conflicts - mark task `needs-human`
- **Harness timeout:** Coding agent took too long - mark task `needs-human`
- **Post API fails:** Platform rate limit or auth error - retry with backoff, then pause for human

## Data Flow

### Task Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Comment   │────>│    Task     │────>│  In-Flight  │────>│  Completed  │
│  (middleman)│     │   (kata)    │     │  (worker)   │     │   (kata)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                  │                   │                    │
       │                  │                   │                    │
    Triage            Claim/            Execute/              Finalize
    creates           Assign            Pause/Post            Close
```

### Kata Labels

| Label | Meaning |
|-------|---------|
| `from-mr` | Task originated from MR comment |
| `nd` | Task is for nd processing |
| `in-progress` | Worker has claimed and is processing |
| `needs-spec` | Low confidence, spec created, awaiting review |
| `addressed` | Code changes made, awaiting response approval |
| `responded` | Response posted to MR |
| `needs-human` | Automation failed, requires manual intervention |
| `failed` | Task could not be completed |

### Dedupe Key Format

```
{platform}:{host}:{owner}/{repo}:mr:{number}:note:{note_id}
```

Example: `gitlab:gitlab.com:myorg/myrepo:mr:123:note:456789`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTFIELD_URL` | `http://localhost:8080` | Control plane URL |
| `TRIAGE_MODEL` | `openrouter/anthropic/claude-sonnet-4` | Model for triage classification |
| `WORKER_MODEL` | `openrouter/anthropic/claude-sonnet-4` | Model for worker analysis/drafting |
| `MIDDLEMAN_URL` | `http://localhost:8091` | Middleman API URL |
| `MIDDLEMAN_DB` | `~/.middleman/middleman.db` | Middleman SQLite path (for direct queries) |
| `KATA_SERVER` | (unix socket) | Kata daemon URL |
| `CONFIDENCE_THRESHOLD` | `70` | Min confidence for auto-processing |
| `ROBOREV_MAX_ITERATIONS` | `3` | Max roborev fix iterations |
| `POLL_INTERVAL_TRIAGE` | `*/5 * * * *` | Triage cron schedule |
| `POLL_INTERVAL_WORKER` | `* * * * *` | Worker cron schedule |
| `AGENT_INSTANCE_ID` | `worker-1` | Unique ID for worker instance |
| `GITHUB_TOKEN` | - | GitHub API token for posting |
| `GITLAB_TOKEN` | - | GitLab API token for posting |

### Kata Project Setup

Each repository tracked in middleman needs a corresponding kata project:

```bash
# Initialize kata project for a repo
cd /path/to/repo
kata init
```

The project name defaults to the repo name, which is used for task routing.

## Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  agentfield:
    image: agentfield/control-plane:latest
    ports:
      - "8080:8080"
    volumes:
      - agentfield-data:/data
    environment:
      - DATABASE_URL=sqlite:///data/agentfield.db

  triage:
    image: nd:latest
    command: python -m nd.triage
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - MIDDLEMAN_URL=http://host.docker.internal:8091
    depends_on:
      - agentfield

  worker-1:
    image: nd:latest
    command: python -m nd.worker
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - AGENT_INSTANCE_ID=worker-1
    depends_on:
      - agentfield

  worker-2:
    image: nd:latest
    command: python -m nd.worker
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - AGENT_INSTANCE_ID=worker-2
    depends_on:
      - agentfield

volumes:
  agentfield-data:
```

### Scaling Workers

To add more workers, either:
1. Add more `worker-N` services to docker-compose
2. Use `docker compose up --scale worker=N` with a template service
3. Deploy to Kubernetes with a Deployment and N replicas

Each worker instance must have a unique `AGENT_INSTANCE_ID` for kata assignment tracking.

## Observability

### AgentField Control Plane UI

- **Workflow DAG:** Visual representation of triage → worker call chains
- **Paused Executions:** Queue of items awaiting human approval
- **Execution History:** Audit trail of all reasoner invocations
- **Agent Health:** Heartbeat status of triage and worker agents

### Logging

Each agent logs to stdout with structured JSON:

```json
{
  "timestamp": "2026-05-27T10:30:00Z",
  "level": "info",
  "agent": "nd-worker",
  "instance": "worker-1",
  "execution_id": "exec-abc123",
  "reasoner": "process_task",
  "task_id": "kata#xyz789",
  "message": "Task processing complete",
  "duration_ms": 45000
}
```

### Metrics

Expose Prometheus metrics at `/metrics`:

- `nd_tasks_created_total` - Counter of tasks created by triage
- `nd_tasks_processed_total` - Counter of tasks processed by workers
- `nd_tasks_by_status` - Gauge by status (completed, failed, paused)
- `nd_processing_duration_seconds` - Histogram of task processing time
- `nd_roborev_iterations` - Histogram of roborev iteration counts
- `nd_pause_duration_seconds` - Histogram of time spent awaiting approval

## Security Considerations

### Secrets Management

- API tokens (GitHub, GitLab) stored in environment variables, never in code
- AgentField control plane handles token injection for `app.pause()` webhooks
- Middleman tokens configured separately in middleman's config

### Code Execution

- Worker uses `app.harness()` which runs a sandboxed coding agent
- Harness has access to: read, write, edit, bash (limited)
- No network access from harness except to roborev daemon
- Git operations limited to the specific MR branch

### Audit Trail

- All executions recorded in AgentField control plane with verifiable credentials
- Kata maintains event history for all task mutations
- Git commits include task ID reference for traceability

## Future Enhancements

### Phase 2: Confidence-Gated Auto-Posting

Once the system proves reliable:
1. Add `AUTO_POST_THRESHOLD` env var (default 100 = never auto-post)
2. Lower threshold gradually (e.g., 90, 80, 70)
3. Monitor post-hoc audit for quality issues
4. Adjust threshold based on error rate

### Phase 3: Real-Time Triggers

Replace cron polling with webhook triggers:
1. Configure middleman `EmbedHooks.OnMRSynced` to call AgentField webhook
2. Convert triage `poll_comments` to `@on_event(source="middleman")`
3. Near real-time response to new comments

### Phase 4: Cross-MR Coordination

For users with many open MRs:
1. Add priority scoring to triage (urgency, reviewer seniority, MR age)
2. Workers process highest-priority tasks first
3. Batch related tasks on same MR for efficiency

### Phase 5: Learning Loop

Improve confidence calibration:
1. Track approval/rejection rates by confidence score
2. Retrain confidence model on historical data
3. Adjust thresholds dynamically per repository/domain

## Appendix: Reasoner Dependency Graph

```
Triage Agent:
  poll_comments (entry, cron)
    ├── classify_actionable (parallel, per comment)
    └── create_task (sequential, for actionable)

Worker Agent:
  claim_task (entry, cron)
    └── process_task
          ├── analyze_task
          ├── plan_changes (if low confidence)
          │     └── app.pause() [spec review]
          ├── execute_changes (via app.harness)
          ├── run_roborev
          │     └── app.pause() [if failed]
          ├── draft_response
          ├── request_post_approval
          │     └── app.pause() [always]
          ├── post_response
          └── finalize_task
```

## Appendix: Example Pause Context

### Spec Review Pause

```json
{
  "type": "spec_review",
  "task_id": "kata#abc123",
  "mr_url": "https://gitlab.com/org/repo/-/merge_requests/456",
  "original_comment": "Can you refactor this to use the new auth service?",
  "analysis": {
    "complexity": 4,
    "confidence": 55,
    "reasoning": "Request involves architectural change to auth flow"
  },
  "spec": {
    "summary": "Refactor authentication to use new auth service",
    "problem_statement": "Current code uses legacy auth directly...",
    "proposed_solution": "1. Add auth service client\n2. Replace direct calls...",
    "files_to_modify": ["src/api/auth.py", "src/middleware/auth.py"],
    "risks": ["Breaking change if old auth removed prematurely"],
    "questions": ["Should we maintain backward compatibility?"]
  }
}
```

### Response Approval Pause

```json
{
  "type": "response_approval",
  "task_id": "kata#abc123",
  "mr_url": "https://gitlab.com/org/repo/-/merge_requests/456",
  "original_comment": "This log message should include the user ID",
  "response_draft": "Addressed in abc1234.\n\nAdded user_id to the log context...",
  "commit_sha": "abc1234",
  "commit_diff": "diff --git a/src/api/handler.py...",
  "changes_summary": [
    "Modified src/api/handler.py: Added user_id to log context"
  ]
}
```
