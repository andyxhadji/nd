"""Unit tests for MRComment.from_dict with activity endpoint format."""

import pytest
from datetime import datetime, UTC

from nd.clients.middleman import MRComment


class TestActivityEndpointFormat:
    """Test that MRComment.from_dict handles activity endpoint response format."""

    def test_from_dict_with_activity_endpoint_format(self):
        """Test parsing activity endpoint response with item_* fields and nested repo."""
        # Real activity endpoint response format
        activity_item = {
            "id": "pre:204790",
            "activity_type": "comment",
            "repo": {
                "provider": "github",
                "platform_host": "github.com",
                "owner": "kenn-io",
                "name": "middleman",
            },
            "platform_host": "github.com",
            "repo_owner": "kenn-io",
            "repo_name": "middleman",
            "item_type": "pr",
            "item_number": 398,
            "item_title": "Expose opt-in pprof listener",
            "item_url": "https://github.com/kenn-io/middleman/pull/398",
            "item_state": "open",
            "author": "roborev-ci[bot]",
            "created_at": "2026-05-29T17:04:37Z",
            "body_preview": "<!-- roborev-pr-comment -->...",
            "body": "Full comment text here",
            "dedupe_key": "comment-4577797327",
            "mr_author": "mariusvniekerk",
            "mr_number": 398,
            "head_branch": "feat/opt-in-pprof-listener",
            "base_branch": "main",
        }

        comment = MRComment.from_dict(activity_item)

        assert comment.id == "pre:204790"
        assert comment.body == "Full comment text here"
        assert comment.author == "roborev-ci[bot]"
        assert comment.created_at == datetime(2026, 5, 29, 17, 4, 37, tzinfo=UTC)
        assert comment.dedupe_key == "comment-4577797327"
        assert comment.mr_number == 398
        assert comment.mr_title == "Expose opt-in pprof listener"
        assert comment.mr_url == "https://github.com/kenn-io/middleman/pull/398"
        assert comment.head_branch == "feat/opt-in-pprof-listener"
        assert comment.base_branch == "main"
        assert comment.platform == "github"
        assert comment.platform_host == "github.com"
        assert comment.repo_owner == "kenn-io"
        assert comment.repo_name == "middleman"

    def test_from_dict_with_direct_format(self):
        """Test parsing direct comment format with mr_* fields (backwards compatibility)."""
        # Original direct comment format
        direct_comment = {
            "id": "1",
            "body": "Please fix this",
            "author": "reviewer1",
            "created_at": "2026-05-29T10:00:00Z",
            "dedupe_key": "comment:1",
            "mr_number": 42,
            "mr_title": "Feature",
            "mr_url": "https://github.com/org/repo/pull/42",
            "head_branch": "feature",
            "base_branch": "main",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "org",
            "repo_name": "repo",
        }

        comment = MRComment.from_dict(direct_comment)

        assert comment.id == "1"
        assert comment.body == "Please fix this"
        assert comment.author == "reviewer1"
        assert comment.dedupe_key == "comment:1"
        assert comment.mr_number == 42
        assert comment.mr_title == "Feature"
        assert comment.mr_url == "https://github.com/org/repo/pull/42"
        assert comment.head_branch == "feature"
        assert comment.base_branch == "main"
        assert comment.platform == "github"
        assert comment.platform_host == "github.com"
        assert comment.repo_owner == "org"
        assert comment.repo_name == "repo"

    def test_from_dict_prefers_direct_fields_over_nested(self):
        """Test that direct fields take precedence over nested repo fields."""
        mixed_format = {
            "id": "1",
            "body": "Test",
            "author": "tester",
            "created_at": "2026-05-29T10:00:00Z",
            "dedupe_key": "comment:1",
            "mr_number": 42,
            "mr_title": "Title",
            "mr_url": "https://github.com/org/repo/pull/42",
            "head_branch": "feature",
            "base_branch": "main",
            # Direct fields should win
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "direct-owner",
            "repo_name": "direct-repo",
            # Nested repo object
            "repo": {
                "provider": "gitlab",
                "platform_host": "gitlab.com",
                "owner": "nested-owner",
                "name": "nested-repo",
            },
        }

        comment = MRComment.from_dict(mixed_format)

        # Direct fields should be used
        assert comment.platform == "github"
        assert comment.platform_host == "github.com"
        assert comment.repo_owner == "direct-owner"
        assert comment.repo_name == "direct-repo"

    def test_from_dict_falls_back_to_nested_repo(self):
        """Test fallback to nested repo object when direct fields are missing."""
        nested_only = {
            "id": "1",
            "body": "Test",
            "author": "tester",
            "created_at": "2026-05-29T10:00:00Z",
            "dedupe_key": "comment:1",
            "item_number": 42,
            "item_title": "Title",
            "item_url": "https://github.com/org/repo/pull/42",
            "head_branch": "feature",
            "base_branch": "main",
            "mr_number": 42,
            # Only nested repo object
            "repo": {
                "provider": "github",
                "platform_host": "github.com",
                "owner": "nested-owner",
                "name": "nested-repo",
            },
        }

        comment = MRComment.from_dict(nested_only)

        # Should use nested repo fields
        assert comment.platform == "github"
        assert comment.platform_host == "github.com"
        assert comment.repo_owner == "nested-owner"
        assert comment.repo_name == "nested-repo"
