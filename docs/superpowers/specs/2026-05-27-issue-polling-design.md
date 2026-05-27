# Issue Polling for nd-triage

## Summary

Add issue polling to nd-triage so it can create kata tasks for open issues assigned to configurable usernames. Requires adding assignee tracking to middleman first.

## Motivation

Currently nd-triage only monitors MR comments. Users also receive work via GitHub/GitLab issues assigned to them. This feature allows nd to triage assigned issues the same way it triages MR comments.

## Design

### Part 1: Middleman Changes

#### Database Migration

Add `assignees_json` column to store issue assignees:

```sql
-- 000028_add_issue_assignees.up.sql
ALTER TABLE middleman_issues ADD COLUMN assignees_json TEXT NOT NULL DEFAULT '[]';
```

#### Sync Logic

**GitHub** (`internal/github/sync.go` or `normalize.go`):
- Extract `assignees` array from issue API response
- Each assignee has a `login` field
- Store as JSON array: `["fh-ahadjigeorgiou", "otheruser"]`

**GitLab/Gitea** (`internal/platform/gitealike/`):
- Extract assignees from issue response (field name may vary by platform)
- Normalize to same JSON array format

#### API Changes

**`GET /api/v1/issues`** - Add `assignee` query parameter:

```go
// internal/server/huma_routes.go
type listIssuesInput struct {
    Repo     string `query:"repo"`
    State    string `query:"state"`
    Starred  bool   `query:"starred"`
    Q        string `query:"q"`
    Assignee string `query:"assignee"`  // NEW
    Limit    int    `query:"limit"`
    Offset   int    `query:"offset"`
}
```

Filter implementation:
```go
if input.Assignee != "" {
    // JSON array contains the username
    filter.Assignee = input.Assignee
}
```

Database query addition:
```sql
AND (? = '' OR assignees_json LIKE '%"' || ? || '"%')
```

#### Frontend Changes

**Issue detail view** (`frontend/`):
- Display assignees in the metadata section
- Show username(s) as chips or simple text

### Part 2: nd-triage Changes

#### Configuration

New environment variable:

```python
# nd/config.py
assigned_usernames: list[str]  # from ND_ASSIGNED_USERNAMES

@classmethod
def from_env(cls) -> "Config":
    return cls(
        # ... existing fields ...
        assigned_usernames=os.getenv("ND_ASSIGNED_USERNAMES", "").split(",")
            if os.getenv("ND_ASSIGNED_USERNAMES") else [],
    )
```

Docker compose:
```yaml
environment:
  - ND_ASSIGNED_USERNAMES=${ND_ASSIGNED_USERNAMES:-}
```

#### Middleman Client

Add method to fetch assigned issues:

```python
# nd/clients/middleman.py

@dataclass
class Issue:
    """An issue from middleman."""
    id: str
    number: int
    title: str
    body: str
    author: str
    url: str
    state: str
    assignees: list[str]
    created_at: datetime
    updated_at: datetime
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str

    @classmethod
    def from_dict(cls, data: dict) -> "Issue":
        # Parse from API response
        ...

class MiddlemanClient:
    async def get_issues_assigned_to(
        self,
        assignee: str,
        state: str = "open",
    ) -> list[Issue]:
        """Fetch issues assigned to a user."""
        client = await self._get_client()
        params = {
            "assignee": assignee,
            "state": state,
        }
        response = await client.get("/api/v1/issues", params=params)
        response.raise_for_status()

        return [Issue.from_dict(item) for item in response.json()]
```

#### New Reasoner

```python
# nd/triage/agent.py

@app.reasoner(tags=["entry"])
# @on_schedule("*/10 * * * *")  # Disabled - trigger manually
async def poll_issues() -> dict:
    """
    Poll middleman for open issues assigned to configured usernames.
    Creates kata tasks for actionable issues.
    """
    if not config.assigned_usernames:
        return PollResult(
            comments_found=0,
            tasks_created=0,
            skipped=0,
            errors=["No assigned usernames configured"],
        ).model_dump()

    total_found = 0
    tasks_created = 0
    skipped = 0
    errors: list[str] = []

    for username in config.assigned_usernames:
        try:
            issues = await middleman.get_issues_assigned_to(
                assignee=username,
                state="open",
            )
        except Exception as e:
            errors.append(f"Middleman error for {username}: {e}")
            continue

        total_found += len(issues)

        for issue in issues:
            # Build dedupe key from issue URL
            dedupe_key = f"issue:{issue.platform}:{issue.platform_host}:{issue.repo_owner}:{issue.repo_name}:{issue.number}"

            # Check for existing task
            existing = await kata.search(issue.repo_name, dedupe_key)
            if existing:
                skipped += 1
                continue

            # Create task
            task_input = TaskInput(
                comment_body=issue.body,
                comment_author=issue.author,
                comment_dedupe_key=dedupe_key,
                mr_number=issue.number,
                mr_title=issue.title,
                mr_url=issue.url,
                head_branch="",  # Not applicable for issues
                base_branch="",
                platform=issue.platform,
                platform_host=issue.platform_host,
                repo_owner=issue.repo_owner,
                repo_name=issue.repo_name,
                classification=ClassificationResult(
                    actionable=True,
                    reason="Assigned issue",
                    category="request",
                    confident=True,
                ),
            )

            result = await app.call(
                f"{app.node_id}.create_task",
                **task_input.model_dump(),
            )
            result = TaskCreationResult(**result)

            if result.created:
                tasks_created += 1
            elif result.skipped_reason != "duplicate":
                errors.append(f"Failed to create task: {result.skipped_reason}")

    return PollResult(
        comments_found=total_found,
        tasks_created=tasks_created,
        skipped=skipped,
        errors=errors,
    ).model_dump()
```

#### Task Body Format

Reuse `KataClient.build_task_body()` with issue-specific adaptations:
- "MR" becomes "Issue" in display
- `head_branch`/`base_branch` omitted or marked N/A
- Category defaults to "request"

## Implementation Order

1. **Middleman: Database migration** - Add assignees_json column
2. **Middleman: Sync logic** - Extract assignees during GitHub/GitLab sync
3. **Middleman: API filter** - Add ?assignee= to /issues endpoint
4. **Middleman: Frontend** - Display assignees in issue detail
5. **nd: Config** - Add ND_ASSIGNED_USERNAMES
6. **nd: Client** - Add get_issues_assigned_to() method
7. **nd: Reasoner** - Add poll_issues reasoner
8. **nd: Docker** - Add env var to docker-compose

## Testing

### Middleman
- Unit test: assignee filter query
- E2E test: sync issues with assignees, query by assignee

### nd-triage
- Unit test: poll_issues with mocked middleman responses
- Functional test: end-to-end issue → task flow

## Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `ND_ASSIGNED_USERNAMES` | Comma-separated usernames to poll | `fh-ahadjigeorgiou,andyxhadji` |

## Open Questions

None - design is complete.
