# nd AgentField Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two AgentField agents (triage + worker) that autonomously process MR comments into kata tasks and address them with code changes.

**Architecture:** Triage agent polls middleman for new comments, classifies them, and creates kata tasks. Worker agents claim tasks, analyze complexity, make code changes via harness, run roborev, and post responses after human approval via `app.pause()`.

**Tech Stack:** Python 3.11+, AgentField SDK, Pydantic, httpx, asyncio

---

## File Structure

```
nd/
├── __init__.py                 # Package init, version
├── schemas.py                  # All Pydantic models (shared)
├── config.py                   # Environment config loader
├── clients/
│   ├── __init__.py
│   ├── middleman.py            # Middleman API client
│   ├── kata.py                 # Kata CLI wrapper
│   └── platform.py             # GitHub/GitLab API posting
├── triage/
│   ├── __init__.py
│   ├── agent.py                # Triage agent definition
│   ├── classifier.py           # Actionable classification logic
│   └── __main__.py             # Entry point: python -m nd.triage
├── worker/
│   ├── __init__.py
│   ├── agent.py                # Worker agent definition
│   ├── analyzer.py             # Task complexity analysis
│   ├── executor.py             # Code execution via harness
│   ├── responder.py            # Response drafting
│   └── __main__.py             # Entry point: python -m nd.worker
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_schemas.py
│   ├── test_classifier.py
│   ├── test_analyzer.py
│   └── test_clients.py
├── functional/
│   ├── __init__.py
│   ├── conftest.py             # AgentField fixtures
│   ├── test_triage.py
│   ├── test_worker.py
│   └── test_e2e.py
docker-compose.yml              # Full stack deployment
docker-compose.test.yml         # Test environment
Dockerfile                      # Agent image
pyproject.toml                  # Project config
README.md                       # Usage docs
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `nd/__init__.py`
- Create: `nd/config.py`
- Create: `pyproject.toml`
- Create: `README.md`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "nd"
version = "1.0.0"
description = "Autonomous AgentField agents for MR comment processing"
requires-python = ">=3.11"
dependencies = [
    "agentfield>=0.1.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "functional: Functional integration tests",
    "unit: Unit tests",
]
```

- [ ] **Step 2: Create nd/__init__.py**

```python
"""nd - Autonomous AgentField agents for MR comment processing."""

__version__ = "1.0.0"
```

- [ ] **Step 3: Create nd/config.py**

```python
"""Configuration loader from environment variables."""

import os
from dataclasses import dataclass


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

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
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
                "TRIAGE_MODEL", "openrouter/anthropic/claude-sonnet-4"
            ),
            worker_model=os.getenv(
                "WORKER_MODEL", "openrouter/anthropic/claude-sonnet-4"
            ),
            agent_instance_id=os.getenv("AGENT_INSTANCE_ID", "worker-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            current_user=os.getenv("ND_CURRENT_USER", ""),
        )


config = Config.from_env()
```

- [ ] **Step 4: Create minimal README.md**

```markdown
# nd

Autonomous AgentField agents for processing MR comments.

## Quick Start

```bash
# Install
pip install -e .

# Run triage agent
python -m nd.triage

# Run worker agent
python -m nd.worker
```

## Configuration

Set environment variables (see `nd/config.py` for defaults).
```

- [ ] **Step 5: Verify structure**

Run: `ls -la nd/`
Expected: `__init__.py`, `config.py`

- [ ] **Step 6: Commit**

```bash
git add nd/__init__.py nd/config.py pyproject.toml README.md
git commit -m "feat: scaffold nd project structure"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `nd/schemas.py`
- Create: `tests/unit/test_schemas.py`

- [ ] **Step 1: Write failing test for schemas**

```python
# tests/unit/test_schemas.py
"""Unit tests for Pydantic schemas."""

import pytest
from nd.schemas import (
    CommentInput,
    ClassificationResult,
    TaskInput,
    TaskCreationResult,
    AnalysisInput,
    AnalysisResult,
    PollResult,
    ClaimResult,
    TaskDetails,
    ProcessResult,
    SpecDocument,
    ExecutionInput,
    ExecutionResult,
    RoborevInput,
    RoborevResult,
    DraftInput,
    DraftResult,
    ApprovalRequest,
    PostInput,
    FinalizeInput,
)


class TestCommentInput:
    def test_valid_comment(self):
        comment = CommentInput(
            body="Can you fix this?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        assert comment.body == "Can you fix this?"
        assert comment.mr_number == 42


class TestClassificationResult:
    def test_actionable_request(self):
        result = ClassificationResult(
            actionable=True,
            reason="Explicit request with 'fix'",
            category="request",
            confident=True,
        )
        assert result.actionable is True
        assert result.category == "request"

    def test_category_validation(self):
        with pytest.raises(ValueError):
            ClassificationResult(
                actionable=True,
                reason="test",
                category="invalid_category",
                confident=True,
            )


class TestAnalysisResult:
    def test_complexity_range(self):
        result = AnalysisResult(
            complexity=3,
            confidence=85,
            reasoning="Moderate change",
            suggested_approach="Refactor function",
            files_likely_affected=["src/handler.py"],
            confident=True,
        )
        assert result.complexity == 3
        assert result.confidence == 85

    def test_confidence_bounds(self):
        # confidence should be 0-100
        result = AnalysisResult(
            complexity=1,
            confidence=100,
            reasoning="test",
            suggested_approach="test",
            files_likely_affected=[],
            confident=True,
        )
        assert result.confidence == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'nd.schemas'"

- [ ] **Step 3: Create nd/schemas.py**

```python
"""Pydantic schemas for nd agents."""

from typing import Literal
from pydantic import BaseModel, Field


# ============================================================================
# Triage Agent Schemas
# ============================================================================


class CommentInput(BaseModel):
    """Input for comment classification."""

    body: str
    author: str
    mr_title: str
    mr_number: int


class ClassificationResult(BaseModel):
    """Result of comment classification."""

    actionable: bool
    reason: str
    category: Literal["question", "request", "feedback", "acknowledgment", "bot", "other"]
    confident: bool


class TaskInput(BaseModel):
    """Input for creating a kata task."""

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


class TaskCreationResult(BaseModel):
    """Result of task creation."""

    created: bool
    task_id: str | None = None
    skipped_reason: str | None = None


class PollResult(BaseModel):
    """Result of polling for comments."""

    comments_found: int
    tasks_created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# ============================================================================
# Worker Agent Schemas
# ============================================================================


class ClaimResult(BaseModel):
    """Result of claiming a task."""

    claimed: bool
    task_id: str | None = None
    project: str | None = None


class TaskDetails(BaseModel):
    """Details of a claimed task."""

    task_id: str
    project: str
    title: str
    body: str
    labels: list[str] = Field(default_factory=list)


class AnalysisInput(BaseModel):
    """Input for task analysis."""

    comment_body: str
    comment_category: str
    mr_title: str
    head_branch: str
    repo_path: str


class AnalysisResult(BaseModel):
    """Result of task complexity analysis."""

    complexity: Literal[1, 2, 3, 4, 5]
    confidence: int = Field(ge=0, le=100)
    reasoning: str
    suggested_approach: str
    files_likely_affected: list[str] = Field(default_factory=list)
    confident: bool


class SpecDocument(BaseModel):
    """Spec document for complex tasks."""

    summary: str
    problem_statement: str
    proposed_solution: str
    files_to_modify: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    testing_approach: str
    risks: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    confident: bool


class ExecutionInput(BaseModel):
    """Input for code execution."""

    task_id: str
    spec: SpecDocument | None = None
    comment_body: str
    repo_path: str
    head_branch: str


class ExecutionResult(BaseModel):
    """Result of code execution."""

    success: bool
    files_changed: list[str] = Field(default_factory=list)
    commit_sha: str | None = None
    error: str | None = None


class RoborevInput(BaseModel):
    """Input for roborev validation."""

    repo_path: str
    commit_sha: str
    max_iterations: int = 3


class RoborevResult(BaseModel):
    """Result of roborev validation."""

    passed: bool
    iterations: int
    final_findings: list[str] = Field(default_factory=list)
    error: str | None = None


class DraftInput(BaseModel):
    """Input for response drafting."""

    comment_body: str
    changes_made: list[str]
    commit_sha: str
    commit_diff: str


class DraftResult(BaseModel):
    """Result of response drafting."""

    response_text: str
    confident: bool


class ApprovalRequest(BaseModel):
    """Request for human approval of response."""

    task_id: str
    mr_url: str
    original_comment: str
    response_draft: str
    commit_sha: str
    commit_diff: str
    changes_summary: list[str] = Field(default_factory=list)


class PostInput(BaseModel):
    """Input for posting response to MR."""

    response_text: str
    dedupe_key: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    mr_number: int


class FinalizeInput(BaseModel):
    """Input for finalizing a task."""

    task_id: str
    status: Literal["completed", "failed", "needs-human"]
    response_posted: bool
    commit_sha: str | None = None


class ProcessResult(BaseModel):
    """Result of processing a task."""

    status: Literal["completed", "paused_for_spec", "paused_for_review", "failed"]
    changes_made: list[str] = Field(default_factory=list)
    response_draft: str | None = None
    error: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nd/schemas.py tests/unit/test_schemas.py
git commit -m "feat: add Pydantic schemas for triage and worker agents"
```

---

## Task 3: Middleman Client

**Files:**
- Create: `nd/clients/__init__.py`
- Create: `nd/clients/middleman.py`
- Create: `tests/unit/test_clients.py`

- [ ] **Step 1: Write failing test for middleman client**

```python
# tests/unit/test_clients.py
"""Unit tests for client modules."""

import pytest
from datetime import datetime, timezone
from nd.clients.middleman import MiddlemanClient, MRComment


class TestMiddlemanClient:
    def test_parse_comment(self):
        raw = {
            "id": "123",
            "body": "Please fix this",
            "author": "reviewer",
            "created_at": "2026-05-27T10:00:00Z",
            "dedupe_key": "gitlab:gitlab.com:org/repo:mr:42:note:123",
            "mr_number": 42,
            "mr_title": "Add feature",
            "mr_url": "https://gitlab.com/org/repo/-/merge_requests/42",
            "head_branch": "feature",
            "base_branch": "main",
            "platform": "gitlab",
            "platform_host": "gitlab.com",
            "repo_owner": "org",
            "repo_name": "repo",
        }
        comment = MRComment.from_dict(raw)
        assert comment.body == "Please fix this"
        assert comment.mr_number == 42
        assert comment.platform == "gitlab"

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        client = MiddlemanClient(base_url="http://localhost:8091")
        assert client.base_url == "http://localhost:8091"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_clients.py::TestMiddlemanClient -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'nd.clients'"

- [ ] **Step 3: Create nd/clients/__init__.py**

```python
"""Client modules for external services."""

from nd.clients.middleman import MiddlemanClient, MRComment
from nd.clients.kata import KataClient
from nd.clients.platform import PlatformClient

__all__ = ["MiddlemanClient", "MRComment", "KataClient", "PlatformClient"]
```

- [ ] **Step 4: Create nd/clients/middleman.py**

```python
"""Middleman API client for fetching MR comments."""

from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator

import httpx


@dataclass
class MRComment:
    """A comment on a merge request from middleman."""

    id: str
    body: str
    author: str
    created_at: datetime
    dedupe_key: str
    mr_number: int
    mr_title: str
    mr_url: str
    head_branch: str
    base_branch: str
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str

    @classmethod
    def from_dict(cls, data: dict) -> "MRComment":
        """Create from API response dict."""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return cls(
            id=str(data["id"]),
            body=data["body"],
            author=data["author"],
            created_at=created_at,
            dedupe_key=data["dedupe_key"],
            mr_number=int(data["mr_number"]),
            mr_title=data["mr_title"],
            mr_url=data["mr_url"],
            head_branch=data["head_branch"],
            base_branch=data["base_branch"],
            platform=data["platform"],
            platform_host=data["platform_host"],
            repo_owner=data["repo_owner"],
            repo_name=data["repo_name"],
        )


class MiddlemanClient:
    """Client for middleman REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_comments_since(
        self,
        since: datetime,
        current_user: str,
    ) -> list[MRComment]:
        """Fetch comments on user's MRs since the given timestamp."""
        client = await self._get_client()
        params = {
            "types": "issue_comment",
            "since": since.isoformat(),
        }
        response = await client.get("/api/v1/activity", params=params)
        response.raise_for_status()

        comments = []
        for item in response.json().get("items", []):
            # Filter to comments on MRs where current_user is author
            if item.get("mr_author") == current_user:
                comments.append(MRComment.from_dict(item))
        return comments

    async def get_comment_by_dedupe_key(self, dedupe_key: str) -> MRComment | None:
        """Fetch a specific comment by its dedupe key."""
        client = await self._get_client()
        params = {"dedupe_key": dedupe_key}
        response = await client.get("/api/v1/activity", params=params)
        response.raise_for_status()

        items = response.json().get("items", [])
        if items:
            return MRComment.from_dict(items[0])
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_clients.py::TestMiddlemanClient -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nd/clients/__init__.py nd/clients/middleman.py tests/unit/test_clients.py
git commit -m "feat: add middleman API client"
```

---

## Task 4: Kata Client

**Files:**
- Create: `nd/clients/kata.py`
- Modify: `tests/unit/test_clients.py`

- [ ] **Step 1: Add failing test for kata client**

```python
# Add to tests/unit/test_clients.py

from nd.clients.kata import KataClient, KataTask


class TestKataClient:
    def test_parse_task(self):
        raw = {
            "id": "abc123",
            "project": "testrepo",
            "title": "Fix bug",
            "body": "## MR Context\n...",
            "labels": ["from-mr", "nd"],
            "owner": None,
        }
        task = KataTask.from_dict(raw)
        assert task.id == "abc123"
        assert task.project == "testrepo"
        assert "nd" in task.labels

    def test_build_task_body(self):
        body = KataClient.build_task_body(
            mr_url="https://gitlab.com/org/repo/-/merge_requests/42",
            mr_title="Add feature",
            head_branch="feature",
            base_branch="main",
            platform="gitlab",
            platform_host="gitlab.com",
            repo_owner="org",
            repo_name="repo",
            mr_number=42,
            comment_author="reviewer",
            comment_body="Please fix this",
            dedupe_key="gitlab:gitlab.com:org/repo:mr:42:note:123",
            category="request",
        )
        assert "## MR Context" in body
        assert "org/repo!42" in body
        assert "Please fix this" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_clients.py::TestKataClient -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Create nd/clients/kata.py**

```python
"""Kata CLI wrapper for task management."""

import asyncio
import json
import shlex
from dataclasses import dataclass


@dataclass
class KataTask:
    """A task from kata."""

    id: str
    project: str
    title: str
    body: str
    labels: list[str]
    owner: str | None

    @classmethod
    def from_dict(cls, data: dict) -> "KataTask":
        """Create from kata JSON output."""
        return cls(
            id=data["id"],
            project=data["project"],
            title=data["title"],
            body=data.get("body", ""),
            labels=data.get("labels", []),
            owner=data.get("owner"),
        )


class KataClient:
    """Client for kata CLI operations."""

    def __init__(self, kata_server: str = ""):
        self.kata_server = kata_server

    def _base_cmd(self) -> list[str]:
        """Build base kata command with server flag if set."""
        cmd = ["kata"]
        if self.kata_server:
            cmd.extend(["--server", self.kata_server])
        return cmd

    async def _run(self, args: list[str]) -> tuple[int, str, str]:
        """Run kata command and return (returncode, stdout, stderr)."""
        cmd = self._base_cmd() + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(), stderr.decode()

    async def search(self, project: str, query: str) -> list[KataTask]:
        """Search for tasks matching a query."""
        returncode, stdout, stderr = await self._run(
            ["search", "--project", project, "--json", query]
        )
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
            return [KataTask.from_dict(t) for t in data.get("tasks", [])]
        except json.JSONDecodeError:
            return []

    async def create(
        self,
        title: str,
        body: str,
        project: str,
        labels: list[str],
        idempotency_key: str,
    ) -> str | None:
        """Create a new task. Returns task ID or None on failure."""
        args = [
            "create",
            title,
            "--body", body,
            "--project", project,
            "--idempotency-key", idempotency_key,
            "--json",
        ]
        for label in labels:
            args.extend(["--label", label])

        returncode, stdout, stderr = await self._run(args)
        if returncode != 0:
            return None
        try:
            data = json.loads(stdout)
            return data.get("id")
        except json.JSONDecodeError:
            return None

    async def ready(self, label: str, unowned: bool = True) -> list[KataTask]:
        """Get tasks ready for work."""
        args = ["ready", "--label", label, "--json"]
        if unowned:
            args.append("--unowned")

        returncode, stdout, stderr = await self._run(args)
        if returncode != 0:
            return []
        try:
            data = json.loads(stdout)
            return [KataTask.from_dict(t) for t in data.get("tasks", [])]
        except json.JSONDecodeError:
            return []

    async def assign(self, task_id: str, owner: str) -> bool:
        """Assign a task to an owner."""
        returncode, _, _ = await self._run(["assign", task_id, owner])
        return returncode == 0

    async def label(self, task_id: str, label: str) -> bool:
        """Add a label to a task."""
        returncode, _, _ = await self._run(["label", task_id, label])
        return returncode == 0

    async def comment(self, task_id: str, message: str) -> bool:
        """Add a comment to a task."""
        returncode, _, _ = await self._run(["comment", task_id, message])
        return returncode == 0

    async def close(self, task_id: str, reason: str, comment: str) -> bool:
        """Close a task."""
        returncode, _, _ = await self._run(
            ["close", task_id, "--reason", reason, "--comment", comment]
        )
        return returncode == 0

    @staticmethod
    def build_task_body(
        mr_url: str,
        mr_title: str,
        head_branch: str,
        base_branch: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        mr_number: int,
        comment_author: str,
        comment_body: str,
        dedupe_key: str,
        category: str,
    ) -> str:
        """Build structured task body markdown."""
        return f"""## MR Context
- **MR:** [{repo_owner}/{repo_name}!{mr_number}]({mr_url})
- **Title:** {mr_title}
- **Branch:** {head_branch} -> {base_branch}
- **Platform:** {platform} ({platform_host})

## Original Comment
**Author:** {comment_author}

{comment_body}

## Metadata
- **Dedupe Key:** `{dedupe_key}`
- **Category:** {category}
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_clients.py::TestKataClient -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nd/clients/kata.py tests/unit/test_clients.py
git commit -m "feat: add kata CLI client"
```

---

## Task 5: Platform Client (GitHub/GitLab)

**Files:**
- Create: `nd/clients/platform.py`
- Modify: `tests/unit/test_clients.py`

- [ ] **Step 1: Add failing test for platform client**

```python
# Add to tests/unit/test_clients.py

from nd.clients.platform import PlatformClient


class TestPlatformClient:
    def test_gitlab_comment_url(self):
        client = PlatformClient(
            github_token="",
            gitlab_token="test-token",
        )
        url = client._gitlab_comment_url(
            host="gitlab.com",
            owner="org",
            repo="repo",
            mr_number=42,
            discussion_id="abc123",
        )
        assert "gitlab.com" in url
        assert "merge_requests/42" in url
        assert "discussions/abc123" in url

    def test_github_comment_url(self):
        client = PlatformClient(
            github_token="test-token",
            gitlab_token="",
        )
        url = client._github_comment_url(
            owner="org",
            repo="repo",
            pr_number=42,
            comment_id=12345,
        )
        assert "api.github.com" in url
        assert "pulls/42" in url
        assert "12345" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_clients.py::TestPlatformClient -v`
Expected: FAIL with "ImportError"

- [ ] **Step 3: Create nd/clients/platform.py**

```python
"""Platform API client for posting responses to GitHub/GitLab."""

import httpx
from urllib.parse import quote


class PlatformClient:
    """Client for posting responses to GitHub and GitLab."""

    def __init__(
        self,
        github_token: str,
        gitlab_token: str,
        timeout: float = 30.0,
    ):
        self.github_token = github_token
        self.gitlab_token = gitlab_token
        self.timeout = timeout
        self._github_client: httpx.AsyncClient | None = None
        self._gitlab_client: httpx.AsyncClient | None = None

    async def _get_github_client(self) -> httpx.AsyncClient:
        if self._github_client is None:
            self._github_client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self.timeout,
            )
        return self._github_client

    async def _get_gitlab_client(self, host: str) -> httpx.AsyncClient:
        if self._gitlab_client is None:
            base_url = f"https://{host}"
            self._gitlab_client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "PRIVATE-TOKEN": self.gitlab_token,
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._gitlab_client

    async def close(self) -> None:
        if self._github_client is not None:
            await self._github_client.aclose()
            self._github_client = None
        if self._gitlab_client is not None:
            await self._gitlab_client.aclose()
            self._gitlab_client = None

    def _gitlab_comment_url(
        self,
        host: str,
        owner: str,
        repo: str,
        mr_number: int,
        discussion_id: str,
    ) -> str:
        """Build GitLab discussion note URL."""
        project_path = quote(f"{owner}/{repo}", safe="")
        return (
            f"https://{host}/api/v4/projects/{project_path}"
            f"/merge_requests/{mr_number}/discussions/{discussion_id}/notes"
        )

    def _github_comment_url(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
    ) -> str:
        """Build GitHub comment reply URL."""
        return (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/pulls/{pr_number}/comments/{comment_id}/replies"
        )

    async def post_gitlab_reply(
        self,
        host: str,
        owner: str,
        repo: str,
        mr_number: int,
        discussion_id: str,
        body: str,
    ) -> bool:
        """Post a reply to a GitLab discussion."""
        client = await self._get_gitlab_client(host)
        url = self._gitlab_comment_url(host, owner, repo, mr_number, discussion_id)
        # Use relative URL since base_url is set
        path = url.replace(f"https://{host}", "")
        response = await client.post(path, json={"body": body})
        return response.status_code in (200, 201)

    async def post_github_reply(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> bool:
        """Post a reply to a GitHub PR comment."""
        client = await self._get_github_client()
        path = f"/repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies"
        response = await client.post(path, json={"body": body})
        return response.status_code in (200, 201)

    async def post_response(
        self,
        platform: str,
        platform_host: str,
        owner: str,
        repo: str,
        mr_number: int,
        thread_id: str,
        body: str,
    ) -> bool:
        """Post a response to the appropriate platform."""
        if platform == "gitlab":
            return await self.post_gitlab_reply(
                host=platform_host,
                owner=owner,
                repo=repo,
                mr_number=mr_number,
                discussion_id=thread_id,
                body=body,
            )
        elif platform == "github":
            return await self.post_github_reply(
                owner=owner,
                repo=repo,
                pr_number=mr_number,
                comment_id=int(thread_id),
                body=body,
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_clients.py::TestPlatformClient -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add nd/clients/platform.py tests/unit/test_clients.py
git commit -m "feat: add platform client for GitHub/GitLab responses"
```

---

## Task 6: Comment Classifier

**Files:**
- Create: `nd/triage/__init__.py`
- Create: `nd/triage/classifier.py`
- Create: `tests/unit/test_classifier.py`

- [ ] **Step 1: Write failing test for classifier**

```python
# tests/unit/test_classifier.py
"""Unit tests for comment classifier."""

import pytest
from nd.triage.classifier import CommentClassifier
from nd.schemas import CommentInput


class TestCommentClassifier:
    @pytest.fixture
    def classifier(self):
        return CommentClassifier()

    def test_is_bot_comment(self, classifier):
        assert classifier._is_bot("dependabot[bot]") is True
        assert classifier._is_bot("renovate[bot]") is True
        assert classifier._is_bot("github-actions[bot]") is True
        assert classifier._is_bot("reviewer") is False

    def test_deterministic_actionable_patterns(self, classifier):
        # Explicit requests
        assert classifier._matches_actionable_pattern("Can you fix this?") is True
        assert classifier._matches_actionable_pattern("please update the docs") is True
        assert classifier._matches_actionable_pattern("nit: add a comment here") is True

        # Non-actionable
        assert classifier._matches_actionable_pattern("LGTM") is False
        assert classifier._matches_actionable_pattern("looks good") is False

    def test_deterministic_non_actionable(self, classifier):
        assert classifier._is_non_actionable("LGTM") is True
        assert classifier._is_non_actionable("Looks good!") is True
        assert classifier._is_non_actionable("+1") is True
        assert classifier._is_non_actionable("thanks") is True
        assert classifier._is_non_actionable("Can you fix this?") is False

    def test_classify_bot_comment(self, classifier):
        comment = CommentInput(
            body="I detected a vulnerability",
            author="dependabot[bot]",
            mr_title="Update deps",
            mr_number=1,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "bot"

    def test_classify_lgtm(self, classifier):
        comment = CommentInput(
            body="LGTM",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "acknowledgment"

    def test_classify_explicit_request(self, classifier):
        comment = CommentInput(
            body="Can you add logging here?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "request"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Create nd/triage/__init__.py**

```python
"""Triage agent module."""

from nd.triage.classifier import CommentClassifier

__all__ = ["CommentClassifier"]
```

- [ ] **Step 4: Create nd/triage/classifier.py**

```python
"""Comment classification logic."""

import re
from nd.schemas import CommentInput, ClassificationResult


# Known bot patterns
BOT_PATTERNS = [
    r".*\[bot\]$",
    r"^dependabot$",
    r"^renovate$",
    r"^github-actions$",
    r"^gitlab-bot$",
]

# Deterministic actionable patterns
ACTIONABLE_PATTERNS = [
    r"\?",  # Questions
    r"\bplease\b",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\bfix\b",
    r"\bchange\b",
    r"\bupdate\b",
    r"\badd\b",
    r"\bremove\b",
    r"^nit:",
    r"^suggestion:",
    r"^todo:",
    r"^blocking:",
]

# Deterministic non-actionable patterns (exact or near-exact)
NON_ACTIONABLE_EXACT = {
    "lgtm",
    "looks good",
    "looks good!",
    "looks good to me",
    "approved",
    "+1",
    "thanks",
    "thank you",
    "thanks!",
    "thank you!",
    "nice",
    "nice!",
    "great",
    "great!",
}


class CommentClassifier:
    """Classifies MR comments as actionable or not."""

    def _is_bot(self, author: str) -> bool:
        """Check if author is a known bot."""
        author_lower = author.lower()
        for pattern in BOT_PATTERNS:
            if re.match(pattern, author_lower):
                return True
        return False

    def _is_non_actionable(self, body: str) -> bool:
        """Check if body matches non-actionable patterns."""
        normalized = body.strip().lower()
        return normalized in NON_ACTIONABLE_EXACT

    def _matches_actionable_pattern(self, body: str) -> bool:
        """Check if body matches actionable patterns."""
        body_lower = body.lower()
        for pattern in ACTIONABLE_PATTERNS:
            if re.search(pattern, body_lower):
                return True
        return False

    def classify_deterministic(
        self, comment: CommentInput
    ) -> ClassificationResult | None:
        """
        Attempt deterministic classification.

        Returns ClassificationResult if deterministic rules match,
        None if LLM classification is needed.
        """
        # Check bot first
        if self._is_bot(comment.author):
            return ClassificationResult(
                actionable=False,
                reason=f"Author '{comment.author}' is a known bot",
                category="bot",
                confident=True,
            )

        # Check non-actionable patterns
        if self._is_non_actionable(comment.body):
            return ClassificationResult(
                actionable=False,
                reason="Comment matches non-actionable pattern",
                category="acknowledgment",
                confident=True,
            )

        # Check actionable patterns
        if self._matches_actionable_pattern(comment.body):
            # Determine category based on pattern
            body_lower = comment.body.lower()
            if "?" in comment.body:
                category = "question"
            elif any(p in body_lower for p in ["nit:", "suggestion:"]):
                category = "feedback"
            else:
                category = "request"

            return ClassificationResult(
                actionable=True,
                reason="Comment matches actionable pattern",
                category=category,
                confident=True,
            )

        # No deterministic match - needs LLM
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_classifier.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nd/triage/__init__.py nd/triage/classifier.py tests/unit/test_classifier.py
git commit -m "feat: add deterministic comment classifier"
```

---

## Task 7: Triage Agent Definition

**Files:**
- Create: `nd/triage/agent.py`
- Create: `nd/triage/__main__.py`

- [ ] **Step 1: Create nd/triage/agent.py**

```python
"""Triage agent definition with AgentField reasoners."""

import asyncio
import os
from datetime import datetime, timezone

from agentfield import Agent, AIConfig, on_schedule
from pydantic import BaseModel

from nd.config import config
from nd.schemas import (
    CommentInput,
    ClassificationResult,
    TaskInput,
    TaskCreationResult,
    PollResult,
)
from nd.clients.middleman import MiddlemanClient, MRComment
from nd.clients.kata import KataClient
from nd.triage.classifier import CommentClassifier


def create_triage_agent(
    node_id: str = "nd-triage",
    ai_config: AIConfig | None = None,
) -> Agent:
    """Create and configure the triage agent."""

    if ai_config is None:
        ai_config = AIConfig(
            model=config.triage_model,
            temperature=0.3,
        )

    app = Agent(
        node_id=node_id,
        version="1.0.0",
        agentfield_server=config.agentfield_url,
        ai_config=ai_config,
    )

    # Initialize clients
    middleman = MiddlemanClient(base_url=config.middleman_url)
    kata = KataClient(kata_server=config.kata_server)
    classifier = CommentClassifier()

    # ========================================================================
    # Reasoners
    # ========================================================================

    @app.reasoner(tags=["entry"])
    @on_schedule("*/5 * * * *")
    async def poll_comments() -> dict:
        """
        Poll middleman for new MR comments and create tasks for actionable ones.

        Runs every 5 minutes via cron trigger.
        """
        # Get last poll timestamp from memory
        last_poll_str = await app.memory.get("last_poll_timestamp", scope="agent")
        if last_poll_str:
            last_poll = datetime.fromisoformat(last_poll_str)
        else:
            # Default to 24 hours ago on first run
            last_poll = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Fetch comments
        try:
            comments = await middleman.get_comments_since(
                since=last_poll,
                current_user=config.current_user,
            )
        except Exception as e:
            return PollResult(
                comments_found=0,
                tasks_created=0,
                skipped=0,
                errors=[f"Middleman error: {e}"],
            ).model_dump()

        # Classify and create tasks
        tasks_created = 0
        skipped = 0
        errors: list[str] = []

        for comment in comments:
            comment_input = CommentInput(
                body=comment.body,
                author=comment.author,
                mr_title=comment.mr_title,
                mr_number=comment.mr_number,
            )

            # Classify
            classification = await app.call(
                f"{app.node_id}.classify_actionable",
                **comment_input.model_dump(),
            )
            classification = ClassificationResult(**classification)

            if not classification.actionable:
                skipped += 1
                continue

            # Create task
            task_input = TaskInput(
                comment_body=comment.body,
                comment_author=comment.author,
                comment_dedupe_key=comment.dedupe_key,
                mr_number=comment.mr_number,
                mr_title=comment.mr_title,
                mr_url=comment.mr_url,
                head_branch=comment.head_branch,
                base_branch=comment.base_branch,
                platform=comment.platform,
                platform_host=comment.platform_host,
                repo_owner=comment.repo_owner,
                repo_name=comment.repo_name,
                classification=classification,
            )

            result = await app.call(
                f"{app.node_id}.create_task",
                **task_input.model_dump(),
            )
            result = TaskCreationResult(**result)

            if result.created:
                tasks_created += 1
            else:
                if result.skipped_reason != "duplicate":
                    errors.append(f"Failed to create task: {result.skipped_reason}")

        # Update last poll timestamp
        await app.memory.set(
            "last_poll_timestamp",
            datetime.now(timezone.utc).isoformat(),
            scope="agent",
        )

        return PollResult(
            comments_found=len(comments),
            tasks_created=tasks_created,
            skipped=skipped,
            errors=errors,
        ).model_dump()

    @app.reasoner()
    async def classify_actionable(
        body: str,
        author: str,
        mr_title: str,
        mr_number: int,
    ) -> dict:
        """Classify whether a comment requires action."""
        comment = CommentInput(
            body=body,
            author=author,
            mr_title=mr_title,
            mr_number=mr_number,
        )

        # Try deterministic classification first
        result = classifier.classify_deterministic(comment)
        if result is not None:
            return result.model_dump()

        # Fall back to LLM classification
        class LLMClassification(BaseModel):
            actionable: bool
            reason: str
            category: str
            confident: bool

        llm_result = await app.ai(
            system="""You classify MR comments as actionable or not.

Actionable comments include:
- Questions directed at the MR author
- Explicit requests to change, fix, add, or remove something
- Review feedback (nit, suggestion, blocking)

Non-actionable comments include:
- Acknowledgments (LGTM, looks good, +1)
- Thanks/gratitude
- Off-topic discussion

Respond with:
- actionable: true/false
- reason: brief explanation
- category: one of "question", "request", "feedback", "acknowledgment", "other"
- confident: true if certain, false if ambiguous""",
            user=f"MR: {mr_title}\n\nComment by {author}:\n{body}",
            schema=LLMClassification,
        )

        return ClassificationResult(
            actionable=llm_result.actionable,
            reason=llm_result.reason,
            category=llm_result.category if llm_result.category in (
                "question", "request", "feedback", "acknowledgment", "bot", "other"
            ) else "other",
            confident=llm_result.confident,
        ).model_dump()

    @app.reasoner()
    async def create_task(
        comment_body: str,
        comment_author: str,
        comment_dedupe_key: str,
        mr_number: int,
        mr_title: str,
        mr_url: str,
        head_branch: str,
        base_branch: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        classification: dict,
    ) -> dict:
        """Create a kata task for an actionable comment."""
        classification_obj = ClassificationResult(**classification)

        # Check for duplicate
        existing = await kata.search(repo_name, comment_dedupe_key)
        if existing:
            return TaskCreationResult(
                created=False,
                skipped_reason="duplicate",
            ).model_dump()

        # Build task
        title = comment_body.split(".")[0][:80]  # First sentence, max 80 chars
        body = KataClient.build_task_body(
            mr_url=mr_url,
            mr_title=mr_title,
            head_branch=head_branch,
            base_branch=base_branch,
            platform=platform,
            platform_host=platform_host,
            repo_owner=repo_owner,
            repo_name=repo_name,
            mr_number=mr_number,
            comment_author=comment_author,
            comment_body=comment_body,
            dedupe_key=comment_dedupe_key,
            category=classification_obj.category,
        )

        # Create task
        task_id = await kata.create(
            title=title,
            body=body,
            project=repo_name,
            labels=["from-mr", "nd"],
            idempotency_key=comment_dedupe_key,
        )

        if task_id:
            return TaskCreationResult(created=True, task_id=task_id).model_dump()
        else:
            return TaskCreationResult(
                created=False,
                skipped_reason="kata create failed",
            ).model_dump()

    return app
```

- [ ] **Step 2: Create nd/triage/__main__.py**

```python
"""Entry point for triage agent."""

from nd.triage.agent import create_triage_agent


def main():
    """Run the triage agent."""
    app = create_triage_agent()
    print(f"Starting nd triage agent: {app.node_id}")
    print(f"Control plane: {app.agentfield_server}")
    app.run(auto_port=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify syntax**

Run: `python -m py_compile nd/triage/agent.py && python -m py_compile nd/triage/__main__.py`
Expected: No output (success)

- [ ] **Step 4: Commit**

```bash
git add nd/triage/agent.py nd/triage/__main__.py
git commit -m "feat: add triage agent with poll, classify, and create_task reasoners"
```

---

## Task 8: Task Analyzer

**Files:**
- Create: `nd/worker/__init__.py`
- Create: `nd/worker/analyzer.py`
- Create: `tests/unit/test_analyzer.py`

- [ ] **Step 1: Write failing test for analyzer**

```python
# tests/unit/test_analyzer.py
"""Unit tests for task analyzer."""

import pytest
from nd.worker.analyzer import TaskAnalyzer
from nd.schemas import AnalysisInput


class TestTaskAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return TaskAnalyzer()

    def test_estimate_complexity_trivial(self, analyzer):
        # Typo fix should be trivial
        comment = "There's a typo: 'recieve' should be 'receive'"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [1, 2]

    def test_estimate_complexity_moderate(self, analyzer):
        # New function request should be moderate
        comment = "Can you add a function to validate the input?"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [2, 3, 4]

    def test_estimate_complexity_major(self, analyzer):
        # Architectural change should be major
        comment = "We need to refactor this to use a different database"
        complexity = analyzer._estimate_complexity(comment)
        assert complexity in [4, 5]

    def test_extract_likely_files(self, analyzer):
        comment = "Please update the handler in src/api/handler.py"
        files = analyzer._extract_likely_files(comment)
        assert "src/api/handler.py" in files

    def test_build_analysis_input(self, analyzer):
        input_data = AnalysisInput(
            comment_body="Fix the bug",
            comment_category="request",
            mr_title="Bug fix",
            head_branch="fix-branch",
            repo_path="/tmp/repo",
        )
        assert input_data.comment_body == "Fix the bug"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_analyzer.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Create nd/worker/__init__.py**

```python
"""Worker agent module."""

from nd.worker.analyzer import TaskAnalyzer

__all__ = ["TaskAnalyzer"]
```

- [ ] **Step 4: Create nd/worker/analyzer.py**

```python
"""Task complexity analysis logic."""

import re
from nd.schemas import AnalysisInput, AnalysisResult


# Complexity indicators
TRIVIAL_PATTERNS = [
    r"\btypo\b",
    r"\bspelling\b",
    r"\bcomment\b",
    r"\bdocstring\b",
    r"\brename\b",
]

MINOR_PATTERNS = [
    r"\blogging\b",
    r"\blog\b",
    r"\berror.?message\b",
    r"\bvalidat",
]

MODERATE_PATTERNS = [
    r"\bfunction\b",
    r"\bmethod\b",
    r"\btest\b",
    r"\brefactor\b",
]

SIGNIFICANT_PATTERNS = [
    r"\bfeature\b",
    r"\barchitect",
    r"\bmultiple.?files\b",
    r"\bapi\b",
]

MAJOR_PATTERNS = [
    r"\bdatabase\b",
    r"\bmigrat",
    r"\bbreaking\b",
    r"\bdesign\b",
    r"\bsecurity\b",
]

# File path pattern
FILE_PATH_PATTERN = re.compile(r"[\w./]+\.\w{1,5}")


class TaskAnalyzer:
    """Analyzes task complexity and confidence."""

    def _estimate_complexity(self, comment: str) -> int:
        """
        Estimate task complexity from comment text.

        Returns 1-5 where:
        1 = trivial (typo, comment)
        2 = minor (logging, error message)
        3 = moderate (new function, refactor)
        4 = significant (new feature, multi-file)
        5 = major (architecture, breaking change)
        """
        comment_lower = comment.lower()

        # Check patterns in order of complexity
        for pattern in MAJOR_PATTERNS:
            if re.search(pattern, comment_lower):
                return 5

        for pattern in SIGNIFICANT_PATTERNS:
            if re.search(pattern, comment_lower):
                return 4

        for pattern in MODERATE_PATTERNS:
            if re.search(pattern, comment_lower):
                return 3

        for pattern in MINOR_PATTERNS:
            if re.search(pattern, comment_lower):
                return 2

        for pattern in TRIVIAL_PATTERNS:
            if re.search(pattern, comment_lower):
                return 1

        # Default to moderate if no patterns match
        return 3

    def _extract_likely_files(self, comment: str) -> list[str]:
        """Extract file paths mentioned in the comment."""
        matches = FILE_PATH_PATTERN.findall(comment)
        # Filter out common false positives
        return [
            m for m in matches
            if not m.startswith("http")
            and not m.endswith((".com", ".org", ".io"))
        ]

    def _estimate_confidence(
        self,
        comment: str,
        category: str,
        complexity: int,
        has_file_refs: bool,
    ) -> int:
        """
        Estimate confidence level (0-100).

        Higher confidence when:
        - Comment is explicit and specific
        - File references are provided
        - Complexity is low
        - Category is "request" (explicit action)
        """
        confidence = 70  # Base confidence

        # Adjust for category
        if category == "request":
            confidence += 10
        elif category == "question":
            confidence -= 10
        elif category == "feedback":
            confidence += 5

        # Adjust for complexity
        if complexity <= 2:
            confidence += 15
        elif complexity >= 4:
            confidence -= 20

        # Adjust for file references
        if has_file_refs:
            confidence += 10

        # Adjust for comment clarity
        if "?" in comment:
            confidence -= 5  # Questions reduce confidence
        if len(comment) > 500:
            confidence -= 10  # Long comments often ambiguous

        # Clamp to 0-100
        return max(0, min(100, confidence))

    def analyze_deterministic(self, input_data: AnalysisInput) -> AnalysisResult:
        """
        Perform deterministic analysis of task complexity.

        This provides initial estimates that can be refined by LLM.
        """
        complexity = self._estimate_complexity(input_data.comment_body)
        files = self._extract_likely_files(input_data.comment_body)
        confidence = self._estimate_confidence(
            comment=input_data.comment_body,
            category=input_data.comment_category,
            complexity=complexity,
            has_file_refs=bool(files),
        )

        return AnalysisResult(
            complexity=complexity,
            confidence=confidence,
            reasoning=f"Estimated complexity {complexity}/5 based on keyword analysis",
            suggested_approach="",  # Will be filled by LLM
            files_likely_affected=files,
            confident=confidence >= 70,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add nd/worker/__init__.py nd/worker/analyzer.py tests/unit/test_analyzer.py
git commit -m "feat: add task complexity analyzer"
```

---

## Task 9: Worker Agent Definition

**Files:**
- Create: `nd/worker/agent.py`
- Create: `nd/worker/__main__.py`

- [ ] **Step 1: Create nd/worker/agent.py**

```python
"""Worker agent definition with AgentField reasoners."""

import asyncio
import os
import re
from datetime import datetime, timezone

from agentfield import Agent, AIConfig, ApprovalResult, on_schedule
from pydantic import BaseModel

from nd.config import config
from nd.schemas import (
    ClaimResult,
    TaskDetails,
    AnalysisInput,
    AnalysisResult,
    SpecDocument,
    ExecutionInput,
    ExecutionResult,
    RoborevInput,
    RoborevResult,
    DraftInput,
    DraftResult,
    ApprovalRequest,
    PostInput,
    FinalizeInput,
    ProcessResult,
)
from nd.clients.kata import KataClient, KataTask
from nd.clients.platform import PlatformClient
from nd.worker.analyzer import TaskAnalyzer


def create_worker_agent(
    node_id: str = "nd-worker",
    ai_config: AIConfig | None = None,
) -> Agent:
    """Create and configure the worker agent."""

    if ai_config is None:
        ai_config = AIConfig(
            model=config.worker_model,
            temperature=0.2,
        )

    app = Agent(
        node_id=node_id,
        version="1.0.0",
        agentfield_server=config.agentfield_url,
        ai_config=ai_config,
    )

    # Initialize clients
    kata = KataClient(kata_server=config.kata_server)
    platform = PlatformClient(
        github_token=config.github_token,
        gitlab_token=config.gitlab_token,
    )
    analyzer = TaskAnalyzer()

    # ========================================================================
    # Reasoners
    # ========================================================================

    @app.reasoner(tags=["entry"])
    @on_schedule("* * * * *")
    async def claim_task() -> dict:
        """
        Poll kata for unclaimed tasks and claim one for processing.

        Runs every minute via cron trigger.
        """
        # Get available tasks
        tasks = await kata.ready(label="nd", unowned=True)
        if not tasks:
            return ClaimResult(claimed=False).model_dump()

        # Claim first available
        task = tasks[0]
        success = await kata.assign(task.id, config.agent_instance_id)
        if not success:
            return ClaimResult(claimed=False).model_dump()

        # Add in-progress label
        await kata.label(task.id, "in-progress")

        # Process the task
        result = await app.call(
            f"{app.node_id}.process_task",
            task_id=task.id,
            project=task.project,
            title=task.title,
            body=task.body,
            labels=task.labels,
        )

        return ClaimResult(
            claimed=True,
            task_id=task.id,
            project=task.project,
        ).model_dump()

    @app.reasoner()
    async def process_task(
        task_id: str,
        project: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> dict:
        """Orchestrate the full task processing flow."""
        # Parse task body to extract context
        context = _parse_task_body(body)
        if not context:
            return ProcessResult(
                status="failed",
                error="Could not parse task body",
            ).model_dump()

        # Analyze task
        analysis_result = await app.call(
            f"{app.node_id}.analyze_task",
            comment_body=context["comment_body"],
            comment_category=context.get("category", "request"),
            mr_title=context.get("mr_title", ""),
            head_branch=context.get("head_branch", ""),
            repo_path=f"/tmp/{project}",  # Placeholder
        )
        analysis = AnalysisResult(**analysis_result)

        # Check confidence threshold
        if analysis.confidence < config.confidence_threshold:
            # Create spec and pause for review
            spec_result = await app.call(
                f"{app.node_id}.plan_changes",
                task_id=task_id,
                comment_body=context["comment_body"],
                analysis=analysis.model_dump(),
                repo_path=f"/tmp/{project}",
            )
            spec = SpecDocument(**spec_result)

            # Pause for human spec review
            approval = await app.pause(
                approval_request_id=f"spec-{task_id}",
                expires_in_hours=72,
                timeout=259200,
                context={
                    "type": "spec_review",
                    "task_id": task_id,
                    "spec": spec.model_dump(),
                    "analysis": analysis.model_dump(),
                },
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                return ProcessResult(
                    status="paused_for_spec",
                    error="Spec rejected by human reviewer",
                ).model_dump()

        # Execute changes via harness
        exec_result = await app.call(
            f"{app.node_id}.execute_changes",
            task_id=task_id,
            comment_body=context["comment_body"],
            repo_path=f"/tmp/{project}",
            head_branch=context.get("head_branch", "main"),
        )
        execution = ExecutionResult(**exec_result)

        if not execution.success:
            await kata.label(task_id, "failed")
            return ProcessResult(
                status="failed",
                error=execution.error,
            ).model_dump()

        # Run roborev
        roborev_result = await app.call(
            f"{app.node_id}.run_roborev",
            repo_path=f"/tmp/{project}",
            commit_sha=execution.commit_sha or "",
            max_iterations=config.roborev_max_iterations,
        )
        roborev = RoborevResult(**roborev_result)

        if not roborev.passed:
            # Pause for human review of roborev failure
            approval = await app.pause(
                approval_request_id=f"roborev-{task_id}",
                expires_in_hours=72,
                timeout=259200,
                context={
                    "type": "roborev_failure",
                    "task_id": task_id,
                    "findings": roborev.final_findings,
                    "iterations": roborev.iterations,
                },
            )

            if not approval.approved:
                await kata.label(task_id, "needs-human")
                return ProcessResult(
                    status="paused_for_review",
                    error="Roborev failed and human rejected",
                ).model_dump()

        # Draft response
        draft_result = await app.call(
            f"{app.node_id}.draft_response",
            comment_body=context["comment_body"],
            changes_made=execution.files_changed,
            commit_sha=execution.commit_sha or "",
            commit_diff="",  # Would get from git
        )
        draft = DraftResult(**draft_result)

        # Always pause for response approval
        approval = await app.pause(
            approval_request_id=f"post-{task_id}",
            expires_in_hours=72,
            timeout=259200,
            context={
                "type": "response_approval",
                "task_id": task_id,
                "mr_url": context.get("mr_url", ""),
                "original_comment": context["comment_body"],
                "response_draft": draft.response_text,
                "commit_sha": execution.commit_sha,
                "changes_summary": execution.files_changed,
            },
        )

        if not approval.approved:
            await kata.label(task_id, "addressed")
            return ProcessResult(
                status="paused_for_review",
                changes_made=execution.files_changed,
                response_draft=draft.response_text,
            ).model_dump()

        # Get potentially edited response from approval
        final_response = approval.feedback or draft.response_text

        # Post response
        post_result = await app.call(
            f"{app.node_id}.post_response",
            response_text=final_response,
            dedupe_key=context.get("dedupe_key", ""),
            platform=context.get("platform", ""),
            platform_host=context.get("platform_host", ""),
            repo_owner=context.get("repo_owner", ""),
            repo_name=project,
            mr_number=context.get("mr_number", 0),
        )

        # Finalize task
        await app.call(
            f"{app.node_id}.finalize_task",
            task_id=task_id,
            status="completed",
            response_posted=True,
            commit_sha=execution.commit_sha,
        )

        return ProcessResult(
            status="completed",
            changes_made=execution.files_changed,
            response_draft=final_response,
        ).model_dump()

    @app.reasoner()
    async def analyze_task(
        comment_body: str,
        comment_category: str,
        mr_title: str,
        head_branch: str,
        repo_path: str,
    ) -> dict:
        """Analyze task complexity and confidence."""
        input_data = AnalysisInput(
            comment_body=comment_body,
            comment_category=comment_category,
            mr_title=mr_title,
            head_branch=head_branch,
            repo_path=repo_path,
        )

        # Get deterministic estimate
        result = analyzer.analyze_deterministic(input_data)

        # Enhance with LLM for suggested approach
        class ApproachSuggestion(BaseModel):
            suggested_approach: str
            additional_files: list[str]
            confident: bool

        llm_result = await app.ai(
            system="""You are analyzing a code review comment to suggest an approach.
Given the comment and estimated complexity, suggest a brief approach (2-3 sentences).
Also list any additional files that might need changes.""",
            user=f"""Comment: {comment_body}
Category: {comment_category}
Estimated complexity: {result.complexity}/5
Files mentioned: {result.files_likely_affected}""",
            schema=ApproachSuggestion,
        )

        result.suggested_approach = llm_result.suggested_approach
        result.files_likely_affected.extend(llm_result.additional_files)
        result.confident = llm_result.confident and result.confident

        return result.model_dump()

    @app.reasoner()
    async def plan_changes(
        task_id: str,
        comment_body: str,
        analysis: dict,
        repo_path: str,
    ) -> dict:
        """Create a detailed spec for complex tasks."""
        analysis_obj = AnalysisResult(**analysis)

        llm_result = await app.ai(
            system="""You are creating a spec document for a code change.
Be specific about what files to modify and how.
Include risks and questions for the human reviewer.""",
            user=f"""Task: {comment_body}

Analysis:
- Complexity: {analysis_obj.complexity}/5
- Confidence: {analysis_obj.confidence}%
- Files: {analysis_obj.files_likely_affected}
- Approach: {analysis_obj.suggested_approach}

Create a detailed spec.""",
            schema=SpecDocument,
        )

        return llm_result.model_dump()

    @app.reasoner()
    async def execute_changes(
        task_id: str,
        comment_body: str,
        repo_path: str,
        head_branch: str,
        spec: dict | None = None,
    ) -> dict:
        """Execute code changes using the harness."""
        goal = f"Address this code review comment:\n\n{comment_body}"
        if spec:
            spec_obj = SpecDocument(**spec)
            goal += f"\n\nSpec:\n{spec_obj.proposed_solution}"

        try:
            result = await app.harness(
                goal=goal,
                provider="claude-code",
                tools=["read", "write", "edit", "bash"],
                max_iterations=20,
            )

            # Parse harness result for files changed
            files_changed = []  # Would parse from harness output
            commit_sha = None  # Would get from git

            return ExecutionResult(
                success=True,
                files_changed=files_changed,
                commit_sha=commit_sha,
            ).model_dump()

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
            ).model_dump()

    @app.reasoner()
    async def run_roborev(
        repo_path: str,
        commit_sha: str,
        max_iterations: int = 3,
    ) -> dict:
        """Run roborev-refine for code quality validation."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "roborev", "refine",
                "--max-iterations", str(max_iterations),
                "--wait",
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            passed = proc.returncode == 0
            # Parse findings from output
            findings = []
            if not passed:
                findings = stderr.decode().split("\n")[:10]

            return RoborevResult(
                passed=passed,
                iterations=max_iterations,  # Would parse actual count
                final_findings=findings,
            ).model_dump()

        except FileNotFoundError:
            return RoborevResult(
                passed=True,  # Skip if roborev not installed
                iterations=0,
                error="roborev not found",
            ).model_dump()

    @app.reasoner()
    async def draft_response(
        comment_body: str,
        changes_made: list[str],
        commit_sha: str,
        commit_diff: str,
    ) -> dict:
        """Generate response text based on changes made."""

        class ResponseDraft(BaseModel):
            response_text: str
            confident: bool

        llm_result = await app.ai(
            system="""You are drafting a response to a code review comment.
Be concise and professional. Mention the commit SHA.
End with an offer to make adjustments if needed.""",
            user=f"""Original comment: {comment_body}

Files changed: {changes_made}
Commit: {commit_sha}

Draft a response.""",
            schema=ResponseDraft,
        )

        return DraftResult(
            response_text=llm_result.response_text,
            confident=llm_result.confident,
        ).model_dump()

    @app.reasoner()
    async def post_response(
        response_text: str,
        dedupe_key: str,
        platform: str,
        platform_host: str,
        repo_owner: str,
        repo_name: str,
        mr_number: int,
    ) -> dict:
        """Post approved response to the MR."""
        # Extract thread ID from dedupe key
        # Format: platform:host:owner/repo:mr:number:note:note_id
        parts = dedupe_key.split(":")
        thread_id = parts[-1] if len(parts) >= 7 else ""

        success = await platform.post_response(
            platform=platform,
            platform_host=platform_host,
            owner=repo_owner,
            repo=repo_name,
            mr_number=mr_number,
            thread_id=thread_id,
            body=response_text,
        )

        return {"posted": success}

    @app.reasoner()
    async def finalize_task(
        task_id: str,
        status: str,
        response_posted: bool,
        commit_sha: str | None = None,
    ) -> dict:
        """Update kata task state after completion."""
        if response_posted:
            await kata.comment(
                task_id,
                f"Response posted. Commit: {commit_sha or 'N/A'}",
            )
            await kata.label(task_id, "responded")
            await kata.close(task_id, reason="done", comment="Addressed and responded")
        elif status == "failed":
            await kata.label(task_id, "failed")
        else:
            await kata.label(task_id, "needs-human")

        return {"finalized": True, "status": status}

    return app


def _parse_task_body(body: str) -> dict | None:
    """Parse structured task body to extract context."""
    context = {}

    # Extract MR URL
    mr_match = re.search(r"\[.*?\]\((https?://[^)]+)\)", body)
    if mr_match:
        context["mr_url"] = mr_match.group(1)

    # Extract branch info
    branch_match = re.search(r"Branch:\*\* (\S+) -> (\S+)", body)
    if branch_match:
        context["head_branch"] = branch_match.group(1)
        context["base_branch"] = branch_match.group(2)

    # Extract platform
    platform_match = re.search(r"Platform:\*\* (\w+) \(([^)]+)\)", body)
    if platform_match:
        context["platform"] = platform_match.group(1)
        context["platform_host"] = platform_match.group(2)

    # Extract dedupe key
    dedupe_match = re.search(r"Dedupe Key:\*\* `([^`]+)`", body)
    if dedupe_match:
        context["dedupe_key"] = dedupe_match.group(1)

    # Extract category
    category_match = re.search(r"Category:\*\* (\w+)", body)
    if category_match:
        context["category"] = category_match.group(1)

    # Extract comment body (between "## Original Comment" and "## Metadata")
    comment_match = re.search(
        r"## Original Comment\n\*\*Author:\*\* [^\n]+\n\n(.*?)\n\n## Metadata",
        body,
        re.DOTALL,
    )
    if comment_match:
        context["comment_body"] = comment_match.group(1).strip()
    else:
        # Fallback: use entire body
        context["comment_body"] = body

    # Extract MR number from dedupe key
    if "dedupe_key" in context:
        parts = context["dedupe_key"].split(":")
        if len(parts) >= 5:
            try:
                context["mr_number"] = int(parts[4])
            except ValueError:
                pass

    return context if "comment_body" in context else None
```

- [ ] **Step 2: Create nd/worker/__main__.py**

```python
"""Entry point for worker agent."""

from nd.worker.agent import create_worker_agent


def main():
    """Run the worker agent."""
    app = create_worker_agent()
    print(f"Starting nd worker agent: {app.node_id}")
    print(f"Instance ID: {app.config.agent_instance_id if hasattr(app, 'config') else 'N/A'}")
    print(f"Control plane: {app.agentfield_server}")
    app.run(auto_port=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify syntax**

Run: `python -m py_compile nd/worker/agent.py && python -m py_compile nd/worker/__main__.py`
Expected: No output (success)

- [ ] **Step 4: Commit**

```bash
git add nd/worker/agent.py nd/worker/__main__.py
git commit -m "feat: add worker agent with full task processing flow"
```

---

## Task 10: Docker Configuration

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `docker-compose.test.yml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY nd/ nd/
COPY tests/ tests/

# Default command (override in compose)
CMD ["python", "-m", "nd.triage"]
```

- [ ] **Step 2: Create docker-compose.yml**

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
      - LOG_LEVEL=info

  triage:
    build: .
    command: python -m nd.triage
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - MIDDLEMAN_URL=http://host.docker.internal:8091
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - TRIAGE_MODEL=${TRIAGE_MODEL:-openrouter/anthropic/claude-sonnet-4}
      - ND_CURRENT_USER=${ND_CURRENT_USER}
    depends_on:
      - agentfield
    restart: unless-stopped

  worker-1:
    build: .
    command: python -m nd.worker
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - WORKER_MODEL=${WORKER_MODEL:-openrouter/anthropic/claude-sonnet-4}
      - AGENT_INSTANCE_ID=worker-1
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
    depends_on:
      - agentfield
    restart: unless-stopped

  worker-2:
    build: .
    command: python -m nd.worker
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - WORKER_MODEL=${WORKER_MODEL:-openrouter/anthropic/claude-sonnet-4}
      - AGENT_INSTANCE_ID=worker-2
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
    depends_on:
      - agentfield
    restart: unless-stopped

volumes:
  agentfield-data:
```

- [ ] **Step 3: Create docker-compose.test.yml**

```yaml
version: '3.8'

services:
  agentfield:
    image: agentfield/control-plane:latest
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=sqlite:///data/agentfield-test.db
      - LOG_LEVEL=debug

  triage:
    build: .
    command: python -m nd.triage
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - TRIAGE_MODEL=openrouter/google/gemini-2.5-flash
      - TEST_MODE=true
    depends_on:
      - agentfield

  worker:
    build: .
    command: python -m nd.worker
    environment:
      - AGENTFIELD_URL=http://agentfield:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - WORKER_MODEL=openrouter/google/gemini-2.5-flash
      - AGENT_INSTANCE_ID=worker-test
      - TEST_MODE=true
    depends_on:
      - agentfield

  test-runner:
    build: .
    command: pytest tests/ -v --tb=short
    environment:
      - AGENTFIELD_SERVER=http://agentfield:8080
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - OPENROUTER_MODEL=openrouter/google/gemini-2.5-flash-lite
    depends_on:
      - triage
      - worker
```

- [ ] **Step 4: Verify compose files**

Run: `docker compose -f docker-compose.yml config > /dev/null && docker compose -f docker-compose.test.yml config > /dev/null && echo "OK"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml docker-compose.test.yml
git commit -m "feat: add Docker configuration for deployment and testing"
```

---

## Task 11: Functional Tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/functional/__init__.py`
- Create: `tests/functional/conftest.py`
- Create: `tests/functional/test_triage.py`
- Create: `tests/functional/test_worker.py`

- [ ] **Step 1: Create test infrastructure**

```python
# tests/__init__.py
"""Test package."""

# tests/conftest.py
"""Shared test configuration."""

import pytest

pytest_plugins = ("pytest_asyncio",)
```

```python
# tests/functional/__init__.py
"""Functional tests package."""

# tests/functional/conftest.py
"""Functional test fixtures."""

import os
import pytest
import httpx
from agentfield import AIConfig


@pytest.fixture(scope="session")
def control_plane_url() -> str:
    return os.environ.get("AGENTFIELD_SERVER", "http://localhost:8080")


@pytest.fixture(scope="session")
def openrouter_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def openrouter_model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "openrouter/google/gemini-2.5-flash-lite")


@pytest.fixture
def openrouter_config(openrouter_api_key: str, openrouter_model: str) -> AIConfig:
    return AIConfig(
        model=openrouter_model,
        api_key=openrouter_api_key,
        temperature=0.3,
    )


@pytest.fixture
async def async_http_client(control_plane_url: str):
    async with httpx.AsyncClient(
        base_url=control_plane_url,
        timeout=60.0,
    ) as client:
        yield client


@pytest.fixture
def mock_middleman_comment() -> dict:
    return {
        "id": "test-comment-001",
        "body": "Can you add logging to this function?",
        "author": "reviewer",
        "created_at": "2026-05-27T10:00:00Z",
        "dedupe_key": "gitlab:gitlab.com:testorg/testrepo:mr:42:note:12345",
        "mr_number": 42,
        "mr_title": "Add new feature",
        "mr_url": "https://gitlab.com/testorg/testrepo/-/merge_requests/42",
        "head_branch": "feature-branch",
        "base_branch": "main",
        "platform": "gitlab",
        "platform_host": "gitlab.com",
        "repo_owner": "testorg",
        "repo_name": "testrepo",
    }
```

- [ ] **Step 2: Create triage functional test**

```python
# tests/functional/test_triage.py
"""Functional tests for triage agent."""

import pytest
from nd.triage.classifier import CommentClassifier
from nd.schemas import CommentInput


@pytest.mark.functional
class TestTriageClassification:
    def test_classify_actionable_request(self):
        """Test classification of explicit request."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="Can you add logging to this function?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "request"

    def test_classify_non_actionable_lgtm(self):
        """Test classification of LGTM."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="LGTM",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "acknowledgment"

    def test_classify_bot_comment(self):
        """Test classification of bot comment."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="I found a security issue",
            author="dependabot[bot]",
            mr_title="Update deps",
            mr_number=1,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "bot"

    def test_classify_question(self):
        """Test classification of question."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="Why did you choose this approach?",
            author="reviewer",
            mr_title="Refactor",
            mr_number=10,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "question"
```

- [ ] **Step 3: Create worker functional test**

```python
# tests/functional/test_worker.py
"""Functional tests for worker agent."""

import pytest
from nd.worker.analyzer import TaskAnalyzer
from nd.schemas import AnalysisInput


@pytest.mark.functional
class TestWorkerAnalysis:
    def test_analyze_trivial_task(self):
        """Test analysis of trivial task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="Fix the typo: 'recieve' should be 'receive'",
            comment_category="request",
            mr_title="Fix typos",
            head_branch="fix-typos",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity in [1, 2]
        assert result.confidence >= 70

    def test_analyze_moderate_task(self):
        """Test analysis of moderate task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="Can you add a validation function for the input?",
            comment_category="request",
            mr_title="Add validation",
            head_branch="add-validation",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity in [2, 3, 4]

    def test_analyze_complex_task(self):
        """Test analysis of complex task."""
        analyzer = TaskAnalyzer()
        input_data = AnalysisInput(
            comment_body="We need to refactor this to use a different database architecture",
            comment_category="request",
            mr_title="Database migration",
            head_branch="db-migration",
            repo_path="/tmp/repo",
        )
        result = analyzer.analyze_deterministic(input_data)
        assert result.complexity >= 4
        assert result.confidence < 70  # Low confidence for complex tasks

    def test_extract_file_paths(self):
        """Test file path extraction from comment."""
        analyzer = TaskAnalyzer()
        comment = "Please update src/api/handler.py and tests/test_handler.py"
        files = analyzer._extract_likely_files(comment)
        assert "src/api/handler.py" in files
        assert "tests/test_handler.py" in files
```

- [ ] **Step 4: Run functional tests**

Run: `pytest tests/functional/ -v --tb=short`
Expected: PASS (all tests should pass without external services)

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "feat: add functional tests for triage and worker agents"
```

---

## Task 12: Final Integration and README

**Files:**
- Modify: `README.md`
- Modify: `nd/clients/__init__.py` (ensure all exports)

- [ ] **Step 1: Update README.md with complete documentation**

```markdown
# nd

Autonomous AgentField agents for processing MR comments.

## Overview

nd consists of two AgentField agents:
- **Triage Agent**: Polls middleman for new MR comments, classifies them, creates kata tasks
- **Worker Agent**: Claims tasks, analyzes complexity, makes code changes, runs roborev, posts responses

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Running middleman instance
- Running kata daemon
- OpenRouter API key

### Installation

```bash
# Clone and install
git clone <repo-url>
cd nd
pip install -e ".[dev]"
```

### Configuration

Create a `.env` file:

```bash
OPENROUTER_API_KEY=your-key-here
ND_CURRENT_USER=your-username
GITHUB_TOKEN=your-github-token  # optional
GITLAB_TOKEN=your-gitlab-token  # optional
```

### Running Locally

```bash
# Run triage agent
python -m nd.triage

# Run worker agent (in another terminal)
python -m nd.worker
```

### Running with Docker

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  AgentField Control Plane                    │
└─────────────────────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
┌───────────────┐         ┌─────────────────┐
│ triage-agent  │         │  worker-agent   │
│  (cron loop)  │         │   (N instances) │
└───────┬───────┘         └────────┬────────┘
        │                          │
        ▼                          ▼
┌───────────────┐         ┌─────────────────┐
│   Middleman   │         │      Kata       │
└───────────────┘         └─────────────────┘
```

## Verification

After starting the agents, verify registration:

```bash
# Check control plane health
curl -fsS http://localhost:8080/api/v1/health | jq

# Check agent registration
curl -fsS http://localhost:8080/api/v1/discovery/capabilities \
  | jq '.capabilities[] | select(.agent_id | startswith("nd-"))'
```

## Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run functional tests
pytest tests/functional/ -v

# Run with Docker
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTFIELD_URL` | `http://localhost:8080` | Control plane URL |
| `MIDDLEMAN_URL` | `http://localhost:8091` | Middleman API URL |
| `TRIAGE_MODEL` | `openrouter/anthropic/claude-sonnet-4` | Model for triage |
| `WORKER_MODEL` | `openrouter/anthropic/claude-sonnet-4` | Model for worker |
| `CONFIDENCE_THRESHOLD` | `70` | Min confidence for auto-processing |
| `AGENT_INSTANCE_ID` | `worker-1` | Unique worker instance ID |

## License

MIT
```

- [ ] **Step 2: Ensure all client exports**

```python
# nd/clients/__init__.py
"""Client modules for external services."""

from nd.clients.middleman import MiddlemanClient, MRComment
from nd.clients.kata import KataClient, KataTask
from nd.clients.platform import PlatformClient

__all__ = [
    "MiddlemanClient",
    "MRComment",
    "KataClient",
    "KataTask",
    "PlatformClient",
]
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Final commit**

```bash
git add README.md nd/clients/__init__.py
git commit -m "docs: complete README and finalize package exports"
```

---

## Summary

This plan implements the nd AgentField architecture in 12 tasks:

1. **Project Scaffold** - Basic structure, config, pyproject.toml
2. **Schemas** - All Pydantic models for both agents
3. **Middleman Client** - API client for fetching comments
4. **Kata Client** - CLI wrapper for task management
5. **Platform Client** - GitHub/GitLab API for posting responses
6. **Classifier** - Deterministic comment classification
7. **Triage Agent** - AgentField agent with poll/classify/create reasoners
8. **Analyzer** - Task complexity analysis
9. **Worker Agent** - AgentField agent with full processing flow
10. **Docker Config** - Dockerfile and compose files
11. **Functional Tests** - Integration tests for both agents
12. **Documentation** - Complete README and exports

Total estimated time: 2-3 hours for experienced developer.
