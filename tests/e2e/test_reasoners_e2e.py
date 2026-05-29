"""E2E tests for individual reasoner functions."""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_triage_classify_with_various_inputs(e2e_env):
    """Test classification with various comment types."""
    test_cases = [
        {
            "body": "Could you add tests for this?",
            "expected_actionable": True,
            "expected_category": "request",
        },
        {
            "body": "Thanks for the fix!",
            "expected_actionable": False,
            "expected_category": "acknowledgment",
        },
        {
            "body": "What's the rationale behind this change?",
            "expected_actionable": True,
            "expected_category": "question",
        },
        {
            "body": "nit: missing comma",
            "expected_actionable": True,
            "expected_category": "feedback",
        },
    ]

    for i, case in enumerate(test_cases):
        result = await e2e_env.call(
            "nd-triage.classify_actionable",
            body=case["body"],
            author="reviewer",
            mr_title=f"Test MR {i}",
            mr_number=100 + i,
        )

        assert result["actionable"] == case["expected_actionable"], f"Failed for: {case['body']}"
        assert result["category"] == case["expected_category"], (
            f"Wrong category for: {case['body']}"
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_worker_analyze_complexity_range(e2e_env):
    """Test that analyze_task returns appropriate complexity scores."""
    test_cases = [
        {
            "body": "Fix typo in comment",
            "expected_complexity_max": 2,
        },
        {
            "body": "Add a simple if statement to check null",
            "expected_complexity_max": 3,
        },
        {
            "body": "Refactor this class to use dependency injection and add unit tests",
            "expected_complexity_min": 3,
        },
        {
            "body": "Rewrite the entire module to support async operations with proper error handling, retries, and comprehensive test coverage",
            "expected_complexity_min": 4,
        },
    ]

    for case in test_cases:
        result = await e2e_env.call(
            "nd-worker.analyze_task",
            comment_body=case["body"],
            comment_category="request",
            mr_title="Test analysis",
            head_branch="test",
            repo_path="/tmp/test",
        )

        complexity = result["complexity"]

        if "expected_complexity_max" in case:
            assert complexity <= case["expected_complexity_max"], (
                f"Complexity too high for: {case['body']}"
            )

        if "expected_complexity_min" in case:
            assert complexity >= case["expected_complexity_min"], (
                f"Complexity too low for: {case['body']}"
            )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_worker_draft_response_includes_commit(e2e_env):
    """Test that drafted responses include commit SHA."""
    commit_sha = "deadbeef1234567890abcdef"

    result = await e2e_env.call(
        "nd-worker.draft_response",
        comment_body="Add logging",
        changes_made=["app.py"],
        commit_sha=commit_sha,
        commit_diff="",
    )

    response_text = result["response_text"]
    assert commit_sha[:8] in response_text or commit_sha in response_text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_worker_finalize_task_updates_state(e2e_env, kata_client):
    """Test that finalize_task updates task state correctly."""
    # Create a test task
    task_id = await kata_client.create_task(
        title="Test finalization",
        body="Test task for finalization",
        project="test-repo",
        labels=["nd"],
    )

    # Finalize it
    result = await e2e_env.call(
        "nd-worker.finalize_task",
        task_id=task_id,
        status="completed",
        response_posted=True,
        commit_sha="abc123",
    )

    assert result["finalized"] is True
    assert result["status"] == "completed"

    # Verify task was updated
    task = await kata_client.show_task(task_id)
    assert "responded" in task.get("labels", [])
    # Task should be closed
    assert task.get("status") in ["done", "closed", "completed"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cross_agent_communication(e2e_env):
    """Test that agents can call each other's reasoners."""
    # Triage classification
    triage_result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Add validation",
        author="reviewer",
        mr_title="Feature",
        mr_number=1,
    )

    assert triage_result["actionable"] is True

    # Worker analysis (independent call)
    worker_result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Add validation",
        comment_category=triage_result["category"],
        mr_title="Feature",
        head_branch="main",
        repo_path="/tmp/test",
    )

    assert "complexity" in worker_result
    assert "confidence" in worker_result
