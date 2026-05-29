"""Unit tests for multi-user support in triage agent comment polling."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from nd.clients.middleman import MiddlemanClient, MRComment
from nd.config import Config


class TestMultiUserCommentPolling:
    """Test that comment polling supports multiple current users."""

    @pytest.mark.asyncio
    async def test_get_comments_with_single_user(self):
        """Test filtering comments for a single user."""
        client = MiddlemanClient(base_url="http://test")

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "body": "Please fix this",
                    "author": "reviewer1",
                    "created_at": "2026-05-29T10:00:00Z",
                    "dedupe_key": "comment:1",
                    "mr_number": 42,
                    "mr_title": "Feature",
                    "mr_url": "https://github.com/org/repo/pull/42",
                    "mr_author": "andy",  # Should match
                    "head_branch": "feature",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
                {
                    "id": "2",
                    "body": "Looks good",
                    "author": "reviewer2",
                    "created_at": "2026-05-29T11:00:00Z",
                    "dedupe_key": "comment:2",
                    "mr_number": 43,
                    "mr_title": "Fix",
                    "mr_url": "https://github.com/org/repo/pull/43",
                    "mr_author": "other",  # Should NOT match
                    "head_branch": "fix",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
            ]
        }

        with patch.object(client, '_get_client', return_value=AsyncMock()) as mock_get_client:
            mock_http_client = mock_get_client.return_value
            mock_http_client.get = AsyncMock(return_value=mock_response)

            comments = await client.get_comments_since(
                since=datetime(2026, 5, 29, 0, 0, 0, tzinfo=UTC),
                current_users=["andy"],
            )

            # Should only get the comment on andy's MR
            assert len(comments) == 1
            assert comments[0].id == "1"
            assert comments[0].author == "reviewer1"

    @pytest.mark.asyncio
    async def test_get_comments_with_multiple_users(self):
        """Test filtering comments for multiple users."""
        client = MiddlemanClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "body": "Comment 1",
                    "author": "reviewer1",
                    "created_at": "2026-05-29T10:00:00Z",
                    "dedupe_key": "comment:1",
                    "mr_number": 42,
                    "mr_title": "Feature",
                    "mr_url": "https://github.com/org/repo/pull/42",
                    "mr_author": "andy",  # Should match
                    "head_branch": "feature",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
                {
                    "id": "2",
                    "body": "Comment 2",
                    "author": "reviewer2",
                    "created_at": "2026-05-29T11:00:00Z",
                    "dedupe_key": "comment:2",
                    "mr_number": 43,
                    "mr_title": "Fix",
                    "mr_url": "https://github.com/org/repo/pull/43",
                    "mr_author": "andyxhadji",  # Should match
                    "head_branch": "fix",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
                {
                    "id": "3",
                    "body": "Comment 3",
                    "author": "reviewer3",
                    "created_at": "2026-05-29T12:00:00Z",
                    "dedupe_key": "comment:3",
                    "mr_number": 44,
                    "mr_title": "Update",
                    "mr_url": "https://github.com/org/repo/pull/44",
                    "mr_author": "other",  # Should NOT match
                    "head_branch": "update",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
            ]
        }

        with patch.object(client, '_get_client', return_value=AsyncMock()) as mock_get_client:
            mock_http_client = mock_get_client.return_value
            mock_http_client.get = AsyncMock(return_value=mock_response)

            comments = await client.get_comments_since(
                since=datetime(2026, 5, 29, 0, 0, 0, tzinfo=UTC),
                current_users=["andy", "andyxhadji"],
            )

            # Should get comments on both andy's and andyxhadji's MRs
            assert len(comments) == 2
            assert {c.id for c in comments} == {"1", "2"}

    @pytest.mark.asyncio
    async def test_get_comments_with_no_users_filter(self):
        """Test that passing None or empty list returns all comments."""
        client = MiddlemanClient(base_url="http://test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "body": "Comment 1",
                    "author": "reviewer1",
                    "created_at": "2026-05-29T10:00:00Z",
                    "dedupe_key": "comment:1",
                    "mr_number": 42,
                    "mr_title": "Feature",
                    "mr_url": "https://github.com/org/repo/pull/42",
                    "mr_author": "andy",
                    "head_branch": "feature",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
                {
                    "id": "2",
                    "body": "Comment 2",
                    "author": "reviewer2",
                    "created_at": "2026-05-29T11:00:00Z",
                    "dedupe_key": "comment:2",
                    "mr_number": 43,
                    "mr_title": "Fix",
                    "mr_url": "https://github.com/org/repo/pull/43",
                    "mr_author": "other",
                    "head_branch": "fix",
                    "base_branch": "main",
                    "platform": "github",
                    "platform_host": "github.com",
                    "repo_owner": "org",
                    "repo_name": "repo",
                },
            ]
        }

        with patch.object(client, '_get_client', return_value=AsyncMock()) as mock_get_client:
            mock_http_client = mock_get_client.return_value
            mock_http_client.get = AsyncMock(return_value=mock_response)

            # Test with None
            comments = await client.get_comments_since(
                since=datetime(2026, 5, 29, 0, 0, 0, tzinfo=UTC),
                current_users=None,
            )
            assert len(comments) == 2

            # Test with empty list
            mock_http_client.get = AsyncMock(return_value=mock_response)
            comments = await client.get_comments_since(
                since=datetime(2026, 5, 29, 0, 0, 0, tzinfo=UTC),
                current_users=[],
            )
            assert len(comments) == 2

    def test_config_parses_multiple_current_users(self):
        """Test that Config correctly parses ND_CURRENT_USERS."""
        with patch.dict('os.environ', {
            'AGENTFIELD_URL': 'http://test',
            'MIDDLEMAN_URL': 'http://test',
            'KATA_SERVER': 'http://test',
            'ND_CURRENT_USERS': 'andy,andyxhadji,other',
        }):
            config = Config.from_env()
            assert config.current_users == ['andy', 'andyxhadji', 'other']

    def test_config_falls_back_to_current_user(self):
        """Test that ND_CURRENT_USERS falls back to ND_CURRENT_USER."""
        with patch.dict('os.environ', {
            'AGENTFIELD_URL': 'http://test',
            'MIDDLEMAN_URL': 'http://test',
            'KATA_SERVER': 'http://test',
            'ND_CURRENT_USER': 'andy',
        }, clear=True):
            config = Config.from_env()
            assert config.current_users == ['andy']
            assert config.current_user == 'andy'

    def test_config_handles_whitespace_in_users(self):
        """Test that Config strips whitespace from usernames."""
        with patch.dict('os.environ', {
            'AGENTFIELD_URL': 'http://test',
            'MIDDLEMAN_URL': 'http://test',
            'KATA_SERVER': 'http://test',
            'ND_CURRENT_USERS': ' andy , andyxhadji , other ',
        }):
            config = Config.from_env()
            assert config.current_users == ['andy', 'andyxhadji', 'other']
