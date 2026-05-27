# tests/unit/test_clients.py
"""Unit tests for client modules."""

import pytest
from datetime import datetime, timezone
from nd.clients.middleman import MiddlemanClient, MRComment
from nd.clients.kata import KataClient, KataTask


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
