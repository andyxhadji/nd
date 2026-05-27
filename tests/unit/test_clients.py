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
