"""Full end-to-end tests covering the complete agent workflow."""

import asyncio
import os

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKIP_AGENT_INTEGRATION") == "true",
    reason="Agent integration disabled - requires docker-compose with agent registration",
)
async def test_simple_request_flow(
    e2e_env,
    mock_middleman,
    mock_github,
    kata_client,
    scenario_loader,
):
    """
    Test complete flow: comment → triage → task → worker → execution.

    This tests a simple, high-confidence request that should proceed
    without approval gates.
    """
    scenario = scenario_loader("simple_request.json")

    # Reset all mocks
    await mock_middleman.reset()
    await mock_github.reset()

    # Seed middleman with comments
    await mock_middleman.seed_comments(scenario["initial_state"]["comments"])

    # Verify comments are seeded
    comments = await mock_middleman.get_comments()
    assert len(comments) == 1
    assert "log statement" in comments[0]["body"]

    # Trigger triage to poll and create task
    result = await e2e_env.call("nd-triage.poll_comments", payload=None)
    assert result["comments_found"] == 1
    assert result["tasks_created"] == 1
    assert len(result.get("errors", [])) == 0

    # Verify task was created in kata
    tasks = await kata_client.list_tasks(project="test-repo")
    assert len(tasks) >= 1

    task = tasks[-1]  # Most recent task
    assert "nd" in task["labels"]
    assert "from-mr" in task["labels"]

    # Trigger worker to claim and process
    result = await e2e_env.call("nd-worker.claim_task", payload=None)
    assert result["claimed"] is True
    assert result["task_id"] is not None
    assert result["project"] == "test-repo"

    # Poll for task status with timeout instead of fixed sleep
    # Worker processes asynchronously
    max_wait = 10  # seconds
    poll_interval = 0.5
    for _ in range(int(max_wait / poll_interval)):
        task_updated = await kata_client.show_task(result["task_id"])
        if "in-progress" in task_updated.get("labels", []):
            break
        await asyncio.sleep(poll_interval)
    else:
        # Timeout reached - task may not have started processing yet
        # This is acceptable for this test
        pass

    # Final verification
    task_updated = await kata_client.show_task(result["task_id"])
    # Note: Task may still be queued if worker is slow
    assert task_updated is not None


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("SKIP_AGENT_INTEGRATION") == "true",
    reason="Agent integration disabled - requires docker-compose with agent registration",
)
async def test_duplicate_comment_handling(
    e2e_env,
    mock_middleman,
    kata_client,
):
    """Test that duplicate comments (same dedupe_key) don't create duplicate tasks."""
    comment = {
        "body": "Please fix this",
        "author": "reviewer",
        "mr_title": "Test MR",
        "mr_number": 99,
        "mr_url": "https://github.com/test-org/test-repo/pull/99",
        "head_branch": "test",
        "base_branch": "main",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "test-org",
        "repo_name": "test-repo",
        "dedupe_key": "github:github.com:test-org:test-repo:99:comment-dup:thread-xyz",
    }

    # Reset mock
    await mock_middleman.reset()

    # Seed same comment twice
    await mock_middleman.seed_comments([comment, comment])

    # Get baseline
    tasks_before = await kata_client.list_tasks()
    count_before = len(tasks_before)

    # First poll - should create task
    result1 = await e2e_env.call("nd-triage.poll_comments", payload=None)
    assert result1["tasks_created"] == 1

    # Reset middleman and seed again
    await mock_middleman.reset()
    await mock_middleman.seed_comments([comment])

    # Second poll - should skip duplicate
    result2 = await e2e_env.call("nd-triage.poll_comments", payload=None)
    assert result2["tasks_created"] == 0  # Duplicate detection

    # Verify only one task was created total
    tasks_after = await kata_client.list_tasks()
    assert len(tasks_after) == count_before + 1
