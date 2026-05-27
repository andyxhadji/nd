# tests/unit/test_clients.py
"""Unit tests for client modules."""

import pytest

from nd.clients.kata import KataClient, KataTask
from nd.clients.middleman import Issue, MiddlemanClient, MRComment
from nd.clients.platform import PlatformClient


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
