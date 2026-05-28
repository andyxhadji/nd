"""Unit tests for nd.worker.agent helpers."""

from nd.clients.kata import KataClient
from nd.schemas import WorkspaceResult
from nd.worker.agent import _parse_task_body


class TestParseTaskBody:
    def test_issue_body_extracts_issue_context(self):
        body = KataClient.build_issue_task_body(
            issue_url="https://github.com/octocat/Hello-World/issues/42",
            issue_title="Add new feature",
            issue_number=42,
            platform="github",
            platform_host="github.com",
            repo_owner="octocat",
            repo_name="Hello-World",
            issue_author="alice",
            issue_body="This is the issue description.\n\nWith multiple lines.",
            assignees=["bob"],
        )

        ctx = _parse_task_body(body)
        assert ctx is not None
        assert ctx["category"] == "issue"
        assert ctx["repo_owner"] == "octocat"
        assert ctx["repo_name"] == "Hello-World"
        assert ctx["mr_number"] == 42
        assert ctx["mr_url"] == "https://github.com/octocat/Hello-World/issues/42"
        assert ctx["mr_title"] == "Add new feature"
        assert ctx["platform"] == "github"
        assert ctx["platform_host"] == "github.com"
        assert "This is the issue description." in ctx["comment_body"]
        # Issue tasks must not carry an MR head_branch.
        assert "head_branch" not in ctx

    def test_mr_body_unchanged(self):
        body = KataClient.build_task_body(
            mr_url="https://gitlab.com/org/repo/-/merge_requests/7",
            mr_title="Fix bug",
            head_branch="feature/x",
            base_branch="main",
            platform="gitlab",
            platform_host="gitlab.com",
            repo_owner="org",
            repo_name="repo",
            mr_number=7,
            comment_author="alice",
            comment_body="Please address X",
            dedupe_key="gitlab:gitlab.com:org/repo:mr:7:note:99",
            category="request",
        )

        ctx = _parse_task_body(body)
        assert ctx is not None
        assert ctx["category"] == "request"
        assert ctx["head_branch"] == "feature/x"
        assert ctx["base_branch"] == "main"
        assert ctx["repo_owner"] == "org"
        assert ctx["repo_name"] == "repo"
        assert ctx["mr_number"] == 7
        assert ctx["dedupe_key"] == "gitlab:gitlab.com:org/repo:mr:7:note:99"
        assert ctx["comment_body"] == "Please address X"
        assert ctx["platform"] == "gitlab"
        assert ctx["platform_host"] == "gitlab.com"

    def test_unparseable_body_falls_back_to_full_body(self):
        # An unstructured body still produces a context with comment_body=body.
        ctx = _parse_task_body("just some random text")
        assert ctx is not None
        assert ctx["comment_body"] == "just some random text"


class TestWorkspaceResultShape:
    """The reasoners mint WorkspaceResult dicts that flow through app.call.

    These tests assert the serialized shape so process_task's
    ``WorkspaceResult(**ws_result)`` round-trip stays stable.
    """

    def test_failure_round_trips(self):
        payload = WorkspaceResult(prepared=False, error="boom").model_dump()
        assert payload["prepared"] is False
        assert payload["error"] == "boom"
        assert payload["repo_path"] is None
        assert payload["bare_path"] is None
        assert payload["branch"] is None
        assert payload["base_branch"] is None

        rebuilt = WorkspaceResult(**payload)
        assert rebuilt.prepared is False
        assert rebuilt.error == "boom"
        assert rebuilt.repo_path is None
        assert rebuilt.bare_path is None
        assert rebuilt.branch is None
        assert rebuilt.base_branch is None

    def test_success_round_trips(self):
        original = WorkspaceResult(
            prepared=True,
            repo_path="/var/nd/work/myproj-7by6",
            branch="master",
            base_branch="master",
            bare_path="/var/nd/repos/github.com/octocat/Hello-World.git",
        )
        payload = original.model_dump()
        rebuilt = WorkspaceResult(**payload)
        assert rebuilt.prepared is True
        assert rebuilt.repo_path == "/var/nd/work/myproj-7by6"
        assert rebuilt.branch == "master"
        assert rebuilt.base_branch == "master"
        assert rebuilt.bare_path == "/var/nd/repos/github.com/octocat/Hello-World.git"
        assert rebuilt.error is None
        # The full object must round-trip identically.
        assert rebuilt == original
