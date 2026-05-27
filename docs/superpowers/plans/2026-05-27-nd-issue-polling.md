# nd Issue Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `poll_issues` reasoner to nd-triage that creates kata tasks for open issues assigned to configurable usernames.

**Architecture:** Add `ND_ASSIGNED_USERNAMES` config, add `get_issues_assigned_to()` to middleman client, create `poll_issues` reasoner that queries each username and creates deduped kata tasks.

**Tech Stack:** Python, Pydantic, httpx, AgentField

**Working Directory:** `/Users/andy/.superset/worktrees/99cc5a38-5fb1-4d5b-9c3f-f5182514d4bb/chipped-geranium`

**Prerequisite:** Complete middleman-issue-assignees plan first (middleman must have `?assignee=` filter).

---

### Task 1: Add assigned_usernames to config

**Files:**
- Modify: `nd/config.py`

- [ ] **Step 1: Add assigned_usernames field to Config**

In `nd/config.py`, update the `Config` class:

```python
@dataclass(frozen=True)
class Config:
    """Application configuration from environment."""

    agentfield_url: str
    middleman_url: str
    middleman_db: str
    kata_server: str
    confidence_threshold: int
    roborev_max_iterations: int
    triage_model: str
    worker_model: str
    agent_instance_id: str
    github_token: str
    gitlab_token: str
    current_user: str
    assigned_usernames: list[str]  # NEW

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        usernames_str = os.getenv("ND_ASSIGNED_USERNAMES", "")
        assigned_usernames = [u.strip() for u in usernames_str.split(",") if u.strip()]

        return cls(
            agentfield_url=os.getenv("AGENTFIELD_URL", "http://localhost:8080"),
            middleman_url=os.getenv("MIDDLEMAN_URL", "http://localhost:8091"),
            middleman_db=os.path.expanduser(
                os.getenv("MIDDLEMAN_DB", "~/.middleman/middleman.db")
            ),
            kata_server=os.getenv("KATA_SERVER", ""),
            confidence_threshold=int(os.getenv("CONFIDENCE_THRESHOLD", "70")),
            roborev_max_iterations=int(os.getenv("ROBOREV_MAX_ITERATIONS", "3")),
            triage_model=os.getenv(
                "TRIAGE_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic/claude-sonnet-4-20250514")
            ),
            worker_model=os.getenv(
                "WORKER_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic/claude-sonnet-4-20250514")
            ),
            agent_instance_id=os.getenv("AGENT_INSTANCE_ID", "worker-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            current_user=os.getenv("ND_CURRENT_USER", ""),
            assigned_usernames=assigned_usernames,
        )
```

- [ ] **Step 2: Commit**

```bash
git add nd/config.py
git commit -m "feat(config): add ND_ASSIGNED_USERNAMES setting"
```

---

### Task 2: Add Issue dataclass to middleman client

**Files:**
- Modify: `nd/clients/middleman.py`

- [ ] **Step 1: Add Issue dataclass**

In `nd/clients/middleman.py`, add after the `MRComment` class:

```python
@dataclass
class Issue:
    """An issue from middleman."""

    id: int
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
        """Create from API response dict."""
        created_at = data["CreatedAt"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = data["UpdatedAt"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return cls(
            id=int(data["ID"]),
            number=int(data["Number"]),
            title=data["Title"],
            body=data.get("Body", ""),
            author=data["Author"],
            url=data["URL"],
            state=data["State"],
            assignees=data.get("assignees", []) or [],
            created_at=created_at,
            updated_at=updated_at,
            platform=data.get("platform", "github"),
            platform_host=data.get("platform_host", "github.com"),
            repo_owner=data.get("repo_owner", ""),
            repo_name=data.get("repo_name", ""),
        )
```

- [ ] **Step 2: Commit**

```bash
git add nd/clients/middleman.py
git commit -m "feat(client): add Issue dataclass to middleman client"
```

---

### Task 3: Add get_issues_assigned_to method

**Files:**
- Modify: `nd/clients/middleman.py`
- Test: `tests/unit/test_clients.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_clients.py`:

```python
@pytest.mark.asyncio
async def test_middleman_get_issues_assigned_to():
    """Test fetching issues assigned to a user."""
    with respx.mock:
        respx.get(
            "http://middleman/api/v1/issues",
            params={"assignee": "alice", "state": "open"},
        ).respond(
            json=[
                {
                    "ID": 1,
                    "Number": 42,
                    "Title": "Test issue",
                    "Body": "Issue body",
                    "Author": "author",
                    "URL": "https://github.com/owner/repo/issues/42",
                    "State": "open",
                    "assignees": ["alice"],
                    "CreatedAt": "2026-05-27T10:00:00Z",
                    "UpdatedAt": "2026-05-27T10:00:00Z",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "owner",
                    "repo_name": "repo",
                }
            ]
        )

        client = MiddlemanClient(base_url="http://middleman")
        issues = await client.get_issues_assigned_to(assignee="alice", state="open")
        await client.close()

        assert len(issues) == 1
        assert issues[0].number == 42
        assert issues[0].title == "Test issue"
        assert issues[0].assignees == ["alice"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_clients.py::test_middleman_get_issues_assigned_to -v`
Expected: FAIL (method doesn't exist)

- [ ] **Step 3: Add get_issues_assigned_to method**

In `nd/clients/middleman.py`, add to `MiddlemanClient`:

```python
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_clients.py::test_middleman_get_issues_assigned_to -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nd/clients/middleman.py tests/unit/test_clients.py
git commit -m "feat(client): add get_issues_assigned_to to middleman client"
```

---

### Task 4: Add IssueTaskInput schema

**Files:**
- Modify: `nd/schemas.py`

- [ ] **Step 1: Add IssueTaskInput schema**

In `nd/schemas.py`, add:

```python
class IssueTaskInput(BaseModel):
    """Input for creating a task from an issue."""

    issue_body: str
    issue_author: str
    issue_number: int
    issue_title: str
    issue_url: str
    dedupe_key: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
```

- [ ] **Step 2: Commit**

```bash
git add nd/schemas.py
git commit -m "feat(schemas): add IssueTaskInput schema"
```

---

### Task 5: Add build_issue_task_body to kata client

**Files:**
- Modify: `nd/clients/kata.py`

- [ ] **Step 1: Add build_issue_task_body method**

In `nd/clients/kata.py`, add to `KataClient`:

```python
@staticmethod
def build_issue_task_body(
    issue_url: str,
    issue_title: str,
    issue_number: int,
    platform: str,
    platform_host: str,
    repo_owner: str,
    repo_name: str,
    issue_author: str,
    issue_body: str,
    dedupe_key: str,
) -> str:
    """Build task body from issue metadata."""
    return f"""## Issue

**Issue:** [{repo_owner}/{repo_name}#{issue_number}]({issue_url})
**Title:** {issue_title}

## Original Issue

**Author:** {issue_author}

{issue_body}

## Metadata

- **Platform:** {platform} ({platform_host})
- **Dedupe Key:** `{dedupe_key}`
- **Category:** issue
"""
```

- [ ] **Step 2: Commit**

```bash
git add nd/clients/kata.py
git commit -m "feat(kata): add build_issue_task_body method"
```

---

### Task 6: Add poll_issues reasoner

**Files:**
- Modify: `nd/triage/agent.py`
- Test: `tests/unit/test_triage_poll_issues.py`

- [ ] **Step 1: Create test file**

Create `tests/unit/test_triage_poll_issues.py`:

```python
"""Tests for poll_issues reasoner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from nd.clients.middleman import Issue


@pytest.fixture
def mock_issue():
    """Create a mock issue."""
    return Issue(
        id=1,
        number=42,
        title="Test issue",
        body="Issue body",
        author="author",
        url="https://github.com/owner/repo/issues/42",
        state="open",
        assignees=["alice"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        platform="github",
        platform_host="github.com",
        repo_owner="owner",
        repo_name="repo",
    )


def test_issue_dedupe_key_format(mock_issue):
    """Test dedupe key format for issues."""
    dedupe_key = f"issue:{mock_issue.platform}:{mock_issue.platform_host}:{mock_issue.repo_owner}:{mock_issue.repo_name}:{mock_issue.number}"
    assert dedupe_key == "issue:github:github.com:owner:repo:42"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_triage_poll_issues.py -v`
Expected: PASS

- [ ] **Step 3: Add poll_issues reasoner to agent.py**

In `nd/triage/agent.py`, add after the `poll_comments` reasoner:

```python
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
            # Build dedupe key from issue
            dedupe_key = f"issue:{issue.platform}:{issue.platform_host}:{issue.repo_owner}:{issue.repo_name}:{issue.number}"

            # Check for existing task
            existing = await kata.search(issue.repo_name, dedupe_key)
            if existing:
                skipped += 1
                continue

            # Build task body
            title = issue.title[:80] if len(issue.title) > 80 else issue.title
            body = KataClient.build_issue_task_body(
                issue_url=issue.url,
                issue_title=issue.title,
                issue_number=issue.number,
                platform=issue.platform,
                platform_host=issue.platform_host,
                repo_owner=issue.repo_owner,
                repo_name=issue.repo_name,
                issue_author=issue.author,
                issue_body=issue.body,
                dedupe_key=dedupe_key,
            )

            # Create task
            task_id = await kata.create(
                title=title,
                body=body,
                project=issue.repo_name,
                labels=["from-issue", "nd"],
                idempotency_key=dedupe_key,
            )

            if task_id:
                tasks_created += 1
            else:
                errors.append(f"Failed to create task for issue {issue.number}")

    return PollResult(
        comments_found=total_found,
        tasks_created=tasks_created,
        skipped=skipped,
        errors=errors,
    ).model_dump()
```

- [ ] **Step 4: Add KataClient import if missing**

Ensure this import exists at the top:

```python
from nd.clients.kata import KataClient
```

- [ ] **Step 5: Run unit tests**

Run: `python -m pytest tests/unit/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nd/triage/agent.py tests/unit/test_triage_poll_issues.py
git commit -m "feat(triage): add poll_issues reasoner"
```

---

### Task 7: Update docker-compose with new env var

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add ND_ASSIGNED_USERNAMES to triage service**

In `docker-compose.yml`, update the triage service environment:

```yaml
triage:
  build: .
  command: python -m nd.triage
  environment:
    - AGENTFIELD_URL=http://agentfield:8080
    - MIDDLEMAN_URL=http://host.docker.internal:8091
    - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}
    - TRIAGE_MODEL=${TRIAGE_MODEL:-bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/fa9v3zo70aog}
    - ND_CURRENT_USER=${ND_CURRENT_USER}
    - ND_ASSIGNED_USERNAMES=${ND_ASSIGNED_USERNAMES:-}
  depends_on:
    - agentfield
  restart: unless-stopped
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): add ND_ASSIGNED_USERNAMES env var"
```

---

### Task 8: Update test-local.sh

**Files:**
- Modify: `test-local.sh`

- [ ] **Step 1: Add ND_ASSIGNED_USERNAMES example**

In `test-local.sh`, add to the optional overrides section:

```bash
# Optional: override defaults
# export TRIAGE_MODEL="bedrock/converse/..."
# export WORKER_MODEL="bedrock/converse/..."
# export CONFIDENCE_THRESHOLD=70
# export ROBOREV_MAX_ITERATIONS=3
# export ND_ASSIGNED_USERNAMES="fh-ahadjigeorgiou,andyxhadji"
```

- [ ] **Step 2: Commit**

```bash
git add test-local.sh
git commit -m "docs: add ND_ASSIGNED_USERNAMES example to test-local.sh"
```

---

### Task 9: Integration test

- [ ] **Step 1: Run all unit tests**

Run: `python -m pytest tests/unit/ -v`
Expected: All tests pass

- [ ] **Step 2: Start services for manual test**

```bash
# Terminal 1: Start middleman
cd ~/code/middleman && ./middleman

# Terminal 2: Export creds and start nd
source test-local.sh env
export ND_ASSIGNED_USERNAMES="fh-ahadjigeorgiou,andyxhadji"
docker-compose up -d
```

- [ ] **Step 3: Trigger poll_issues manually**

In AgentField UI (http://localhost:8081), trigger the `poll_issues` reasoner for `nd-triage`.

- [ ] **Step 4: Verify results**

Check the reasoner output - should show issues found (or 0 if none assigned).

---

### Task 10: Final commit and push

- [ ] **Step 1: Review all changes**

Run: `git log --oneline 783d550..HEAD`
Review commit history

- [ ] **Step 2: Push changes**

```bash
git push
```

- [ ] **Step 3: Update PR description**

Add to the PR description:

```markdown
## Additional Changes

- Add `poll_issues` reasoner to triage agent
- Poll middleman for open issues assigned to configured usernames
- Create kata tasks for new assigned issues

## Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `ND_ASSIGNED_USERNAMES` | Comma-separated usernames to poll for assigned issues | `fh-ahadjigeorgiou,andyxhadji` |
```
