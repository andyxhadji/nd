"""Test that triage agent triggers worker claim_task after creating tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nd.triage.agent import create_triage_agent


async def dispatch_reasoner(app, name: str, **kwargs):
    """Helper to invoke reasoners directly from the registry."""
    reasoner_name = name.split(".")[-1]
    return await app._reasoner_registry[reasoner_name].func(**kwargs)


@pytest.fixture
def mock_kata():
    """Mock KataClient with successful create."""
    with patch("nd.triage.agent.KataClient") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.search = AsyncMock(return_value=[])  # No existing task
        mock_instance.create = AsyncMock(return_value="test-task-123")
        mock_instance.close = AsyncMock()
        yield mock_instance


@pytest.fixture
def mock_middleman():
    """Mock MiddlemanClient."""
    with patch("nd.triage.agent.MiddlemanClient") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.close = AsyncMock()
        yield mock_instance


@pytest.mark.asyncio
async def test_create_task_triggers_worker_claim(mock_kata, mock_middleman):
    """Verify create_task calls worker's claim_task after creating a kata task."""
    agent = create_triage_agent(node_id="nd-triage")

    # Mock app.call to track trigger
    agent.call = AsyncMock()

    # Call create_task reasoner
    result = await dispatch_reasoner(
        agent,
        "create_task",
        comment_body="Please add logging",
        comment_author="reviewer",
        comment_dedupe_key="test-key-123",
        mr_number=42,
        mr_title="Add feature",
        mr_url="https://gitlab.com/org/repo/-/merge_requests/42",
        head_branch="feature-branch",
        base_branch="main",
        platform="gitlab",
        platform_host="gitlab.com",
        repo_owner="org",
        repo_name="repo",
        classification={
            "actionable": True,
            "reason": "explicit request",
            "category": "request",
            "confident": True,
        },
    )

    # Verify task was created
    assert result["created"] is True
    assert result["task_id"] == "test-task-123"

    # Verify worker was triggered
    agent.call.assert_awaited_once_with("nd-worker.claim_task", payload=None)


@pytest.mark.asyncio
async def test_create_issue_task_triggers_worker_claim(mock_kata, mock_middleman):
    """Verify create_issue_task calls worker's claim_task after creating a kata task."""
    agent = create_triage_agent(node_id="nd-triage")

    # Mock app.call to track trigger
    agent.call = AsyncMock()

    # Call create_issue_task reasoner
    result = await dispatch_reasoner(
        agent,
        "create_issue_task",
        issue_number=10,
        issue_title="Fix bug",
        issue_body="There's a bug in the code",
        issue_url="https://gitlab.com/org/repo/-/issues/10",
        issue_author="user",
        assignees=["dev1", "dev2"],
        platform="gitlab",
        platform_host="gitlab.com",
        repo_owner="org",
        repo_name="repo",
    )

    # Verify task was created
    assert result["created"] is True
    assert result["task_id"] == "test-task-123"

    # Verify worker was triggered
    agent.call.assert_awaited_once_with("nd-worker.claim_task", payload=None)


@pytest.mark.asyncio
async def test_create_task_handles_trigger_failure_gracefully(mock_kata, mock_middleman):
    """Verify create_task still succeeds even if worker trigger fails."""
    agent = create_triage_agent(node_id="nd-triage")

    # Mock app.call to raise an exception
    agent.call = AsyncMock(side_effect=Exception("Worker unavailable"))

    # Mock print to capture warning
    with patch("builtins.print") as mock_print:
        result = await dispatch_reasoner(
            agent,
            "create_task",
            comment_body="Please add logging",
            comment_author="reviewer",
            comment_dedupe_key="test-key-456",
            mr_number=43,
            mr_title="Add feature",
            mr_url="https://gitlab.com/org/repo/-/merge_requests/43",
            head_branch="feature-branch",
            base_branch="main",
            platform="gitlab",
            platform_host="gitlab.com",
            repo_owner="org",
            repo_name="repo",
            classification={
                "actionable": True,
                "reason": "explicit request",
                "category": "request",
                "confident": True,
            },
        )

        # Task creation should still succeed
        assert result["created"] is True
        assert result["task_id"] == "test-task-123"

        # Verify warning was printed
        mock_print.assert_called_once()
        assert "Warning: Failed to trigger worker" in str(mock_print.call_args)
        assert "test-task-123" in str(mock_print.call_args)


@pytest.mark.asyncio
async def test_create_task_does_not_trigger_on_duplicate(mock_kata, mock_middleman):
    """Verify worker is not triggered when task creation is skipped (duplicate)."""
    agent = create_triage_agent(node_id="nd-triage")

    # Mock kata to return existing task (duplicate)
    mock_kata.search = AsyncMock(return_value=[{"id": "existing-task"}])
    agent.call = AsyncMock()

    result = await dispatch_reasoner(
        agent,
        "create_task",
        comment_body="Please add logging",
        comment_author="reviewer",
        comment_dedupe_key="duplicate-key",
        mr_number=44,
        mr_title="Add feature",
        mr_url="https://gitlab.com/org/repo/-/merge_requests/44",
        head_branch="feature-branch",
        base_branch="main",
        platform="gitlab",
        platform_host="gitlab.com",
        repo_owner="org",
        repo_name="repo",
        classification={
            "actionable": True,
            "reason": "explicit request",
            "category": "request",
            "confident": True,
        },
    )

    # Task creation should be skipped
    assert result["created"] is False
    assert result["skipped_reason"] == "duplicate"

    # Verify worker was NOT triggered
    agent.call.assert_not_awaited()
