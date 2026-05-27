# tests/unit/test_clients.py
"""Unit tests for client modules."""

import json

import httpx
import pytest

from nd.clients.kata import KataClient, KataTask
from nd.clients.middleman import Issue, MiddlemanClient, MRComment
from nd.clients.platform import PlatformClient


class _FakeProc:
    """Minimal stand-in for asyncio subprocess to test KataClient._run."""

    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _patch_kata_subprocess(monkeypatch, *, returncode=0, stdout=b"", stderr=b""):
    """Patch asyncio.create_subprocess_exec to return a fake proc; return captured args."""
    captured: dict = {}

    async def fake_exec(*cmd, stdout=None, stderr=None):
        captured["cmd"] = cmd
        return _FakeProc(
            returncode, stdout=_patch_kata_subprocess._stdout, stderr=_patch_kata_subprocess._stderr
        )

    _patch_kata_subprocess._stdout = stdout
    _patch_kata_subprocess._stderr = stderr
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    return captured


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

    @pytest.mark.asyncio
    async def test_get_issues_assigned_to_handles_bare_array(self):
        """Middleman /api/v1/issues returns a bare JSON array, not {"items": [...]}."""
        raw_issue = {
            "id": "456",
            "number": 123,
            "title": "Bug report",
            "body": "Something is broken",
            "state": "open",
            "author": "reporter",
            "assignees": ["andyxhadji"],
            "url": "https://github.com/org/repo/issues/123",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T11:00:00Z",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "org",
            "repo_name": "repo",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[raw_issue])

        client = MiddlemanClient(base_url="http://middleman")
        client._client = httpx.AsyncClient(
            base_url="http://middleman",
            transport=httpx.MockTransport(handler),
        )

        issues = await client.get_issues_assigned_to("andyxhadji")
        assert len(issues) == 1
        assert issues[0].number == 123
        assert issues[0].assignees == ["andyxhadji"]

        await client.close()

    @pytest.mark.asyncio
    async def test_get_issues_assigned_to_handles_wrapped_object(self):
        """Backwards-compat: also handle {"items": [...]} shape if returned."""
        raw_issue = {
            "id": "456",
            "number": 123,
            "title": "Bug report",
            "body": "Something is broken",
            "state": "open",
            "author": "reporter",
            "assignees": ["andyxhadji"],
            "url": "https://github.com/org/repo/issues/123",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T11:00:00Z",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "org",
            "repo_name": "repo",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": [raw_issue]})

        client = MiddlemanClient(base_url="http://middleman")
        client._client = httpx.AsyncClient(
            base_url="http://middleman",
            transport=httpx.MockTransport(handler),
        )

        issues = await client.get_issues_assigned_to("andyxhadji")
        assert len(issues) == 1
        assert issues[0].number == 123

        await client.close()

    @pytest.mark.asyncio
    async def test_get_issues_assigned_to_empty_array(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        client = MiddlemanClient(base_url="http://middleman")
        client._client = httpx.AsyncClient(
            base_url="http://middleman",
            transport=httpx.MockTransport(handler),
        )

        issues = await client.get_issues_assigned_to("andyxhadji")
        assert issues == []

        await client.close()

    def test_parse_issue(self):
        raw = {
            "id": "456",
            "number": 123,
            "title": "Bug report",
            "body": "Something is broken",
            "state": "open",
            "author": "reporter",
            "assignees": ["user1", "user2"],
            "url": "https://github.com/org/repo/issues/123",
            "created_at": "2026-05-27T10:00:00Z",
            "updated_at": "2026-05-27T11:00:00Z",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "org",
            "repo_name": "repo",
        }
        issue = Issue.from_dict(raw)
        assert issue.number == 123
        assert issue.title == "Bug report"
        assert issue.assignees == ["user1", "user2"]
        assert issue.platform == "github"

    def test_parse_issue_middleman_shape(self):
        """Real middleman /api/v1/issues response uses PascalCase top-level keys
        and nests platform info under 'repo'."""
        raw = {
            "ID": 5894,
            "Number": 11,
            "Title": "Bug: blank board preview",
            "Author": "andyxhadji",
            "State": "open",
            "Body": "When I open the UI, the board preview is blank.",
            "URL": "https://github.com/andyxhadji/sweets/issues/11",
            "CreatedAt": "2026-05-27T18:15:43Z",
            "UpdatedAt": "2026-05-27T18:15:45Z",
            "ClosedAt": None,
            "assignees": ["andyxhadji"],
            "repo": {
                "provider": "github",
                "platform_host": "github.com",
                "owner": "andyxhadji",
                "name": "sweets",
            },
            "platform_host": "github.com",
            "repo_owner": "andyxhadji",
            "repo_name": "sweets",
        }
        issue = Issue.from_dict(raw)
        assert issue.id == "5894"
        assert issue.number == 11
        assert issue.title == "Bug: blank board preview"
        assert issue.body == "When I open the UI, the board preview is blank."
        assert issue.author == "andyxhadji"
        assert issue.state == "open"
        assert issue.assignees == ["andyxhadji"]
        assert issue.url == "https://github.com/andyxhadji/sweets/issues/11"
        assert issue.platform == "github"
        assert issue.platform_host == "github.com"
        assert issue.repo_owner == "andyxhadji"
        assert issue.repo_name == "sweets"
        assert issue.created_at.year == 2026


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

    def test_build_issue_task_body(self):
        body = KataClient.build_issue_task_body(
            issue_url="https://github.com/org/repo/issues/123",
            issue_title="Bug report",
            issue_number=123,
            platform="github",
            platform_host="github.com",
            repo_owner="org",
            repo_name="repo",
            issue_author="reporter",
            issue_body="Something is broken",
            assignees=["user1", "user2"],
        )
        assert "## Issue Context" in body
        assert "org/repo#123" in body
        assert "Something is broken" in body
        assert "user1, user2" in body


class TestKataClientAsync:
    def test_base_cmd_no_server(self):
        client = KataClient()
        assert client._base_cmd() == ["kata"]

    def test_base_cmd_with_server(self):
        client = KataClient(kata_server="kata.local:7000")
        assert client._base_cmd() == ["kata", "--server", "kata.local:7000"]

    @pytest.mark.asyncio
    async def test_run_captures_command_and_output(self, monkeypatch):
        captured = _patch_kata_subprocess(
            monkeypatch, returncode=0, stdout=b"hello", stderr=b"warn"
        )
        client = KataClient(kata_server="srv:1")
        rc, out, err = await client._run(["search", "x"])
        assert rc == 0
        assert out == "hello"
        assert err == "warn"
        assert captured["cmd"] == ("kata", "--server", "srv:1", "search", "x")

    @pytest.mark.asyncio
    async def test_search_returns_tasks(self, monkeypatch):
        payload = {
            "tasks": [
                {"id": "t1", "project": "p", "title": "T1", "labels": ["nd"]},
                {"id": "t2", "project": "p", "title": "T2"},
            ]
        }
        _patch_kata_subprocess(monkeypatch, returncode=0, stdout=json.dumps(payload).encode())
        tasks = await KataClient().search("p", "query")
        assert [t.id for t in tasks] == ["t1", "t2"]
        assert tasks[0].labels == ["nd"]
        assert tasks[1].labels == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_failure(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=1)
        assert await KataClient().search("p", "q") == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_on_invalid_json(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=0, stdout=b"not-json")
        assert await KataClient().search("p", "q") == []

    @pytest.mark.asyncio
    async def test_create_passes_labels_and_returns_id(self, monkeypatch):
        captured = _patch_kata_subprocess(monkeypatch, returncode=0, stdout=b'{"id": "new-task"}')
        task_id = await KataClient().create(
            title="t",
            body="b",
            project="p",
            labels=["a", "b"],
            idempotency_key="key1",
        )
        assert task_id == "new-task"
        cmd = list(captured["cmd"])
        assert "--label" in cmd
        # Two --label entries for two labels
        assert cmd.count("--label") == 2
        assert "--idempotency-key" in cmd

    @pytest.mark.asyncio
    async def test_create_returns_none_on_failure(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=1)
        result = await KataClient().create(
            title="t", body="b", project="p", labels=[], idempotency_key="k"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_create_returns_none_on_invalid_json(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=0, stdout=b"not-json")
        result = await KataClient().create(
            title="t", body="b", project="p", labels=[], idempotency_key="k"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_ready_returns_tasks(self, monkeypatch):
        captured = _patch_kata_subprocess(
            monkeypatch,
            returncode=0,
            stdout=b'{"tasks": [{"id": "r1", "project": "p", "title": "Ready"}]}',
        )
        tasks = await KataClient().ready(label="nd", unowned=True)
        assert [t.id for t in tasks] == ["r1"]
        assert "--unowned" in captured["cmd"]

    @pytest.mark.asyncio
    async def test_ready_omits_unowned_when_false(self, monkeypatch):
        captured = _patch_kata_subprocess(monkeypatch, returncode=0, stdout=b'{"tasks": []}')
        await KataClient().ready(label="nd", unowned=False)
        assert "--unowned" not in captured["cmd"]

    @pytest.mark.asyncio
    async def test_ready_returns_empty_on_failure(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=1)
        assert await KataClient().ready(label="nd") == []

    @pytest.mark.asyncio
    async def test_ready_returns_empty_on_invalid_json(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=0, stdout=b"not-json")
        assert await KataClient().ready(label="nd") == []

    @pytest.mark.asyncio
    async def test_assign_label_comment_close_truthiness(self, monkeypatch):
        _patch_kata_subprocess(monkeypatch, returncode=0)
        client = KataClient()
        assert await client.assign("t1", "alice") is True
        assert await client.label("t1", "x") is True
        assert await client.comment("t1", "msg") is True
        assert await client.close("t1", "done", "ok") is True

        _patch_kata_subprocess(monkeypatch, returncode=2)
        assert await client.assign("t1", "alice") is False
        assert await client.label("t1", "x") is False
        assert await client.comment("t1", "msg") is False
        assert await client.close("t1", "done", "ok") is False


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

    def test_url_escapes_special_characters(self):
        client = PlatformClient(github_token="", gitlab_token="")
        url = client._gitlab_comment_url(
            host="gitlab.com",
            owner="my org",
            repo="my repo",
            mr_number=1,
            discussion_id="d/1",
        )
        # `quote` with safe="" must percent-encode '/'
        assert "my%20org%2Fmy%20repo" in url


class TestPlatformClientAsync:
    @pytest.mark.asyncio
    async def test_post_github_reply_success(self, monkeypatch):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(201, json={"id": 1})

        client = PlatformClient(github_token="gh", gitlab_token="")
        client._github_client = httpx.AsyncClient(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(handler),
        )

        result = await client.post_github_reply(
            owner="o", repo="r", pr_number=10, comment_id=99, body="hello"
        )
        assert result is True
        assert len(calls) == 1
        assert calls[0].url.path == "/repos/o/r/pulls/10/comments/99/replies"
        assert json.loads(calls[0].content) == {"body": "hello"}

        await client.close()

    @pytest.mark.asyncio
    async def test_post_github_reply_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "not found"})

        client = PlatformClient(github_token="gh", gitlab_token="")
        client._github_client = httpx.AsyncClient(
            base_url="https://api.github.com",
            transport=httpx.MockTransport(handler),
        )

        result = await client.post_github_reply(
            owner="o", repo="r", pr_number=10, comment_id=99, body="hello"
        )
        assert result is False
        await client.close()

    @pytest.mark.asyncio
    async def test_post_gitlab_reply_success(self):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(201, json={"id": 1})

        client = PlatformClient(github_token="", gitlab_token="gl")
        client._gitlab_client = httpx.AsyncClient(
            base_url="https://gitlab.example.com",
            transport=httpx.MockTransport(handler),
        )

        result = await client.post_gitlab_reply(
            host="gitlab.example.com",
            owner="o",
            repo="r",
            mr_number=42,
            discussion_id="d1",
            body="reply",
        )
        assert result is True
        assert len(calls) == 1
        assert "merge_requests/42/discussions/d1/notes" in calls[0].url.path
        assert json.loads(calls[0].content) == {"body": "reply"}

        await client.close()

    @pytest.mark.asyncio
    async def test_post_response_dispatches_gitlab(self, monkeypatch):
        client = PlatformClient(github_token="", gitlab_token="gl")
        called: dict = {}

        async def fake_gitlab(**kwargs):
            called.update(kwargs)
            return True

        monkeypatch.setattr(client, "post_gitlab_reply", fake_gitlab)

        result = await client.post_response(
            platform="gitlab",
            platform_host="gitlab.com",
            owner="o",
            repo="r",
            mr_number=1,
            thread_id="d-abc",
            body="b",
        )
        assert result is True
        assert called["discussion_id"] == "d-abc"
        await client.close()

    @pytest.mark.asyncio
    async def test_post_response_dispatches_github(self, monkeypatch):
        client = PlatformClient(github_token="gh", gitlab_token="")
        called: dict = {}

        async def fake_github(**kwargs):
            called.update(kwargs)
            return True

        monkeypatch.setattr(client, "post_github_reply", fake_github)

        result = await client.post_response(
            platform="github",
            platform_host="github.com",
            owner="o",
            repo="r",
            mr_number=1,
            thread_id="12345",
            body="b",
        )
        assert result is True
        assert called["comment_id"] == 12345
        await client.close()

    @pytest.mark.asyncio
    async def test_post_response_github_rejects_non_numeric_thread_id(self):
        client = PlatformClient(github_token="gh", gitlab_token="")
        with pytest.raises(ValueError, match="must be numeric"):
            await client.post_response(
                platform="github",
                platform_host="github.com",
                owner="o",
                repo="r",
                mr_number=1,
                thread_id="not-a-number",
                body="b",
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_post_response_unsupported_platform(self):
        client = PlatformClient(github_token="", gitlab_token="")
        with pytest.raises(ValueError, match="Unsupported platform"):
            await client.post_response(
                platform="bitbucket",
                platform_host="bitbucket.org",
                owner="o",
                repo="r",
                mr_number=1,
                thread_id="1",
                body="b",
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_close_idempotent_without_init(self):
        # Calling close before any client was lazily created must not error
        client = PlatformClient(github_token="", gitlab_token="")
        await client.close()
        await client.close()
