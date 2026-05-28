"""Mocked end-to-end tests for triage and worker agent flows."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from nd.clients.kata import KataClient, KataTask
from nd.clients.middleman import Issue, MRComment
from nd.schemas import (
    AnalysisResult,
    DraftResult,
    ExecutionResult,
    RoborevResult,
)


class FakeMemory:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str):
        self.values[key] = value


async def dispatch_reasoner(app, name: str, **kwargs):
    reasoner_name = name.split(".")[-1]
    return await app._reasoner_registry[reasoner_name].func(**kwargs)


@dataclass
class FakeTriageMiddleman:
    comments: list[MRComment] = field(default_factory=list)
    issues_by_user: dict[str, list[Issue]] = field(default_factory=dict)
    comment_queries: list[dict] = field(default_factory=list)
    issue_queries: list[str] = field(default_factory=list)

    async def get_comments_since(self, *, since: datetime, current_user: str):
        self.comment_queries.append({"since": since, "current_user": current_user})
        return self.comments

    async def get_issues_assigned_to(self, username: str):
        self.issue_queries.append(username)
        return self.issues_by_user.get(username, [])

    async def close(self):
        return None


@dataclass
class FakeTriageKata:
    created: list[dict] = field(default_factory=list)
    existing_queries: set[tuple[str, str]] = field(default_factory=set)

    async def search(self, project: str, query: str):
        if (project, query) in self.existing_queries:
            return [
                KataTask(
                    id=f"{project}#dupe",
                    project=project,
                    title="dupe",
                    body="",
                    labels=[],
                    owner=None,
                )
            ]
        return []

    async def create(
        self, *, title: str, body: str, project: str, labels: list[str], idempotency_key: str
    ):
        task_id = f"{project}#{len(self.created) + 1:04d}"
        self.created.append(
            {
                "task_id": task_id,
                "title": title,
                "body": body,
                "project": project,
                "labels": labels,
                "idempotency_key": idempotency_key,
            }
        )
        return task_id


def fake_triage_kata_factory(fake_kata: FakeTriageKata):
    class FakeTriageKataClient:
        build_task_body = staticmethod(KataClient.build_task_body)
        build_issue_task_body = staticmethod(KataClient.build_issue_task_body)

        def __new__(cls, kata_server: str = ""):
            return fake_kata

    return FakeTriageKataClient


def _triage_config(**overrides):
    values = {
        "triage_model": "test-model",
        "agentfield_url": "http://agentfield",
        "middleman_url": "http://middleman",
        "kata_server": "",
        "current_user": "alice",
        "assigned_usernames": ["alice", "bob"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _make_gitlab_comment(body: str = "Please add a regression test") -> MRComment:
    return MRComment(
        id="note-99",
        body=body,
        author="reviewer",
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
        dedupe_key="gitlab:gitlab.example.com:org/repo:mr:42:discussion:note-99",
        mr_number=42,
        mr_title="Improve parser",
        mr_url="https://gitlab.example.com/org/repo/-/merge_requests/42",
        head_branch="feature/parser",
        base_branch="main",
        platform="gitlab",
        platform_host="gitlab.example.com",
        repo_owner="org",
        repo_name="repo",
    )


def _make_gitlab_issue(number: int = 7) -> Issue:
    return Issue(
        id=str(number),
        number=number,
        title="Fix failing parser edge case",
        body="Parser fails on empty input.",
        state="open",
        author="reporter",
        assignees=["alice", "bob"],
        url=f"https://gitlab.example.com/org/repo/-/issues/{number}",
        created_at=datetime(2026, 5, 27, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 27, 12, 5, tzinfo=UTC),
        platform="gitlab",
        platform_host="gitlab.example.com",
        repo_owner="org",
        repo_name="repo",
    )


@pytest.mark.asyncio
async def test_triage_polls_gitlab_comments_and_creates_kata_task(monkeypatch):
    import nd.triage.agent as triage_agent

    fake_middleman = FakeTriageMiddleman(comments=[_make_gitlab_comment()])
    fake_kata = FakeTriageKata()

    monkeypatch.setattr(triage_agent, "config", _triage_config())
    monkeypatch.setattr(triage_agent, "MiddlemanClient", lambda base_url: fake_middleman)
    monkeypatch.setattr(triage_agent, "KataClient", fake_triage_kata_factory(fake_kata))

    app = triage_agent.create_triage_agent(node_id="triage-test")
    memory = FakeMemory()
    monkeypatch.setattr(type(app), "memory", property(lambda _self: memory))
    monkeypatch.setattr(app, "call", lambda name, **kwargs: dispatch_reasoner(app, name, **kwargs))

    result = await app._reasoner_registry["poll_comments"].func()

    assert result["comments_found"] == 1
    assert result["tasks_created"] == 1
    assert result["errors"] == []
    assert fake_middleman.comment_queries[0]["current_user"] == "alice"
    assert fake_kata.created[0]["project"] == "repo"
    assert fake_kata.created[0]["labels"] == ["from-mr", "nd"]
    assert fake_kata.created[0]["idempotency_key"] == _make_gitlab_comment().dedupe_key
    assert "gitlab.example.com/org/repo/-/merge_requests/42" in fake_kata.created[0]["body"]
    assert "**Branch:** feature/parser -> main" in fake_kata.created[0]["body"]


@pytest.mark.asyncio
async def test_triage_polls_assigned_gitlab_issues_dedupes_and_creates_kata_task(monkeypatch):
    import nd.triage.agent as triage_agent

    issue = _make_gitlab_issue()
    fake_middleman = FakeTriageMiddleman(issues_by_user={"alice": [issue], "bob": [issue]})
    fake_kata = FakeTriageKata()

    monkeypatch.setattr(triage_agent, "config", _triage_config())
    monkeypatch.setattr(triage_agent, "MiddlemanClient", lambda base_url: fake_middleman)
    monkeypatch.setattr(triage_agent, "KataClient", fake_triage_kata_factory(fake_kata))

    app = triage_agent.create_triage_agent(node_id="triage-test")
    monkeypatch.setattr(app, "call", lambda name, **kwargs: dispatch_reasoner(app, name, **kwargs))

    result = await app._reasoner_registry["poll_issues"].func()

    assert result["issues_found"] == 1
    assert result["tasks_created"] == 1
    assert result["skipped"] == 0
    assert fake_middleman.issue_queries == ["alice", "bob"]
    assert fake_kata.created[0]["labels"] == ["from-issue", "nd"]
    assert fake_kata.created[0]["idempotency_key"] == f"issue:{issue.url}"
    assert "## Issue Context" in fake_kata.created[0]["body"]
    assert (
        "[org/repo#7](https://gitlab.example.com/org/repo/-/issues/7)"
        in fake_kata.created[0]["body"]
    )


@dataclass
class FakeWorkerKata:
    ready_tasks: list[KataTask] = field(default_factory=list)
    assigned: list[tuple[str, str]] = field(default_factory=list)
    labels: list[tuple[str, str]] = field(default_factory=list)
    comments: list[tuple[str, str]] = field(default_factory=list)
    closed: list[tuple[str, str, str]] = field(default_factory=list)

    async def ready(self, label: str, unowned: bool = True):
        return self.ready_tasks

    async def assign(self, task_id: str, owner: str):
        self.assigned.append((task_id, owner))
        return True

    async def label(self, task_id: str, label: str):
        self.labels.append((task_id, label))
        return True

    async def comment(self, task_id: str, message: str):
        self.comments.append((task_id, message))
        return True

    async def close(self, task_id: str, reason: str, comment: str):
        self.closed.append((task_id, reason, comment))
        return True


@dataclass
class FakeWorkerWorkspace:
    prepared: list[dict] = field(default_factory=list)
    pushed: list[dict] = field(default_factory=list)
    cleaned: list[tuple[str, str]] = field(default_factory=list)

    async def prepare(self, **kwargs):
        self.prepared.append(kwargs)
        branch = kwargs["head_branch"] or f"nd/issue-{kwargs['issue_short_id']}"
        return SimpleNamespace(
            repo_path="/tmp/nd-work/repo-0007",
            branch=branch,
            base_branch=kwargs["base_branch"] or "main",
            bare_path="/tmp/nd-work/repos/gitlab.example.com/org/repo.git",
        )

    async def push(self, **kwargs):
        self.pushed.append(kwargs)
        return True

    async def cleanup(self, repo_path: str, bare_path: str):
        self.cleaned.append((repo_path, bare_path))
        return True


@dataclass
class FakeWorkerPlatform:
    posted: list[dict] = field(default_factory=list)
    merge_requests: list[dict] = field(default_factory=list)

    async def post_response(self, **kwargs):
        self.posted.append(kwargs)
        return True

    async def create_merge_request(self, **kwargs):
        self.merge_requests.append(kwargs)
        return "https://gitlab.example.com/org/repo/-/merge_requests/99"

    async def close(self):
        return None


class Approved:
    approved = True
    feedback = None


async def approved_pause(**_kwargs):
    return Approved()


def _worker_config(**overrides):
    values = {
        "worker_model": "test-model",
        "agentfield_url": "http://agentfield",
        "kata_server": "",
        "github_token": "",
        "gitlab_token": "gl-token",
        "workspace_root": "/tmp/nd-work",
        "agent_instance_id": "worker-1",
        "confidence_threshold": 70,
        "roborev_max_iterations": 3,
        "workspace_keep_on_failure": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _make_worker_agent(monkeypatch, *, kata=None, workspace=None, platform=None):
    import nd.worker.agent as worker_agent

    fake_kata = kata or FakeWorkerKata()
    fake_workspace = workspace or FakeWorkerWorkspace()
    fake_platform = platform or FakeWorkerPlatform()

    monkeypatch.setattr(worker_agent, "config", _worker_config())
    monkeypatch.setattr(worker_agent, "KataClient", lambda kata_server: fake_kata)
    monkeypatch.setattr(worker_agent, "WorkspaceClient", lambda **kwargs: fake_workspace)
    monkeypatch.setattr(worker_agent, "PlatformClient", lambda **kwargs: fake_platform)

    app = worker_agent.create_worker_agent(node_id="worker-test")
    return app, fake_kata, fake_workspace, fake_platform


@pytest.mark.asyncio
async def test_worker_claims_ready_kata_task_and_starts_processing(monkeypatch):
    task = KataTask(
        id="repo#0007",
        project="repo",
        title="Fix parser",
        body="body",
        labels=["nd"],
        owner=None,
    )
    app, fake_kata, _workspace, _platform = _make_worker_agent(
        monkeypatch, kata=FakeWorkerKata(ready_tasks=[task])
    )
    processed: list[dict] = []

    async def fake_call(name: str, **kwargs):
        if name.endswith(".process_task"):
            processed.append(kwargs)
            return {"status": "completed"}
        return await dispatch_reasoner(app, name, **kwargs)

    monkeypatch.setattr(app, "call", fake_call)

    result = await app._reasoner_registry["claim_task"].func()

    assert result == {"claimed": True, "task_id": "repo#0007", "project": "repo"}
    assert fake_kata.assigned == [("repo#0007", "worker-1")]
    assert fake_kata.labels == [("repo#0007", "in-progress")]
    assert processed[0]["task_id"] == "repo#0007"
    assert processed[0]["project"] == "repo"


@pytest.mark.asyncio
async def test_worker_processes_gitlab_issue_task_pushes_branch_and_creates_mr(monkeypatch):
    issue_body = KataClient.build_issue_task_body(
        issue_url="https://gitlab.example.com/org/repo/-/issues/7",
        issue_title="Fix parser edge case",
        issue_number=7,
        platform="gitlab",
        platform_host="gitlab.example.com",
        repo_owner="org",
        repo_name="repo",
        issue_author="reporter",
        issue_body="Parser fails on empty input.",
        assignees=["alice"],
    )
    app, fake_kata, fake_workspace, fake_platform = _make_worker_agent(monkeypatch)

    async def fake_call(name: str, **kwargs):
        reasoner = name.split(".")[-1]
        if reasoner == "analyze_task":
            return AnalysisResult(
                complexity=2,
                confidence=95,
                reasoning="deterministic",
                suggested_approach="Add the missing parser guard.",
                files_likely_affected=["parser.py"],
                confident=True,
            ).model_dump()
        if reasoner == "execute_changes":
            return ExecutionResult(
                success=True,
                files_changed=["parser.py", "tests/test_parser.py"],
                commit_sha="abc1234",
            ).model_dump()
        if reasoner == "run_roborev":
            return RoborevResult(passed=True, iterations=1).model_dump()
        if reasoner == "draft_response":
            return DraftResult(
                response_text="Opened an MR with the fix.", confident=True
            ).model_dump()
        return await dispatch_reasoner(app, name, **kwargs)

    monkeypatch.setattr(app, "call", fake_call)
    monkeypatch.setattr(app, "pause", approved_pause)

    result = await app._reasoner_registry["process_task"].func(
        task_id="repo#0007",
        project="repo",
        title="Fix parser edge case",
        body=issue_body,
        labels=["from-issue", "nd"],
    )

    assert result["status"] == "completed"
    assert fake_workspace.prepared[0]["issue_short_id"] == "0007"
    assert fake_workspace.prepared[0]["head_branch"] is None
    assert fake_workspace.pushed == [
        {"platform": "gitlab", "repo_path": "/tmp/nd-work/repo-0007", "branch": "nd/issue-0007"}
    ]
    assert fake_platform.merge_requests == [
        {
            "platform": "gitlab",
            "platform_host": "gitlab.example.com",
            "owner": "org",
            "repo": "repo",
            "source_branch": "nd/issue-0007",
            "target_branch": "main",
            "title": "Fix parser edge case",
            "body": "Addresses https://gitlab.example.com/org/repo/-/issues/7",
        }
    ]
    assert fake_platform.posted == []
    assert fake_kata.comments[-1] == (
        "repo#0007",
        "Merge request created: https://gitlab.example.com/org/repo/-/merge_requests/99",
    )
    assert ("repo#0007", "responded") in fake_kata.labels
    assert fake_kata.closed == [("repo#0007", "done", "Addressed and responded")]
    assert fake_workspace.cleaned == [
        ("/tmp/nd-work/repo-0007", "/tmp/nd-work/repos/gitlab.example.com/org/repo.git")
    ]


@pytest.mark.asyncio
async def test_worker_processes_gitlab_mr_task_pushes_branch_and_posts_response(monkeypatch):
    mr_body = KataClient.build_task_body(
        mr_url="https://gitlab.example.com/org/repo/-/merge_requests/42",
        mr_title="Improve parser",
        head_branch="feature/parser",
        base_branch="main",
        platform="gitlab",
        platform_host="gitlab.example.com",
        repo_owner="org",
        repo_name="repo",
        mr_number=42,
        comment_author="reviewer",
        comment_body="Please add a regression test.",
        dedupe_key="gitlab:gitlab.example.com:org/repo:mr:42:discussion:disc-1",
        category="request",
    )
    app, fake_kata, fake_workspace, fake_platform = _make_worker_agent(monkeypatch)

    async def fake_call(name: str, **kwargs):
        reasoner = name.split(".")[-1]
        if reasoner == "analyze_task":
            return AnalysisResult(
                complexity=2,
                confidence=95,
                reasoning="deterministic",
                suggested_approach="Add a regression test.",
                files_likely_affected=["tests/test_parser.py"],
                confident=True,
            ).model_dump()
        if reasoner == "execute_changes":
            return ExecutionResult(
                success=True,
                files_changed=["tests/test_parser.py"],
                commit_sha="def5678",
            ).model_dump()
        if reasoner == "run_roborev":
            return RoborevResult(passed=True, iterations=1).model_dump()
        if reasoner == "draft_response":
            return DraftResult(
                response_text="Added the regression test.", confident=True
            ).model_dump()
        return await dispatch_reasoner(app, name, **kwargs)

    monkeypatch.setattr(app, "call", fake_call)
    monkeypatch.setattr(app, "pause", approved_pause)

    result = await app._reasoner_registry["process_task"].func(
        task_id="repo#0042",
        project="repo",
        title="Please add a regression test",
        body=mr_body,
        labels=["from-mr", "nd"],
    )

    assert result["status"] == "completed"
    assert fake_workspace.prepared[0]["head_branch"] == "feature/parser"
    assert fake_workspace.pushed == [
        {"platform": "gitlab", "repo_path": "/tmp/nd-work/repo-0007", "branch": "feature/parser"}
    ]
    assert fake_platform.merge_requests == []
    assert fake_platform.posted == [
        {
            "platform": "gitlab",
            "platform_host": "gitlab.example.com",
            "owner": "org",
            "repo": "repo",
            "mr_number": 42,
            "thread_id": "disc-1",
            "body": "Added the regression test.",
        }
    ]
    assert fake_kata.comments[-1] == ("repo#0042", "Response posted. Commit: def5678")
