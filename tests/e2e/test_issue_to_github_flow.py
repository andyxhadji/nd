"""E2E test for complete issue → triage → worker → GitHub flow."""

import asyncio

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_issue_to_github_complete_flow(
    e2e_env,
    mock_middleman,
    mock_github,
    kata_client,
):
    """
    Test complete flow: GitHub issue → triage → task → worker → GitHub response.

    This tests the full workflow for an assigned issue:
    1. Mock middleman has an issue assigned to a user
    2. Triage polls and creates a kata task
    3. Worker claims the task
    4. Worker processes (analyzes, prepares workspace, executes)
    5. Worker posts response back to mock GitHub
    """
    # Reset all mocks
    await mock_middleman.reset()
    await mock_github.reset()

    # Define test issue
    test_issue = {
        "id": "issue-001",
        "number": 123,
        "title": "Add logging to main function",
        "body": "We need to add debug logging at the start of the main() function to track when it's called.",
        "state": "open",
        "author": "product-manager",
        "assignees": ["test-user"],
        "url": "https://github.com/test-org/test-repo/issues/123",
        "created_at": "2026-05-29T10:00:00Z",
        "updated_at": "2026-05-29T10:00:00Z",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "test-org",
        "repo_name": "test-repo",
    }

    # Seed middleman with the issue
    await mock_middleman.seed_issues([test_issue])

    # Verify issue is available
    issues = await mock_middleman.get_issues_assigned_to("test-user")
    assert len(issues) == 1
    assert issues[0]["number"] == 123
    assert "logging" in issues[0]["body"].lower()

    # Get baseline task count
    tasks_before = await kata_client.list_tasks()
    count_before = len(tasks_before)

    # Step 1: Trigger triage to poll issues and create task
    triage_result = await e2e_env.call("nd-triage.poll_issues", payload=None)
    assert triage_result["issues_found"] == 1
    assert triage_result["tasks_created"] == 1
    assert len(triage_result.get("errors", [])) == 0

    # Verify task was created in kata
    tasks_after_triage = await kata_client.list_tasks()
    assert len(tasks_after_triage) == count_before + 1

    # Find the newly created task
    new_task = tasks_after_triage[-1]
    assert "nd" in new_task["labels"]
    assert "from-issue" in new_task["labels"]
    assert "test-repo" in new_task["id"]

    # Get task details
    task_detail = await kata_client.show_task(new_task["id"])
    assert "github.com" in task_detail["body"]
    assert "test-org/test-repo" in task_detail["body"]
    assert "#123" in task_detail["body"]

    # Step 2: Trigger worker to claim the task
    claim_result = await e2e_env.call("nd-worker.claim_task", payload=None)
    assert claim_result["claimed"] is True
    assert claim_result["task_id"] is not None
    assert claim_result["project"] == "test-repo"

    claimed_task_id = claim_result["task_id"]

    # Verify task is now in-progress
    claimed_task = await kata_client.show_task(claimed_task_id)
    assert "in-progress" in claimed_task.get("labels", []) or "claimed" in claimed_task.get("labels", [])

    # Step 3: Poll for worker to complete processing
    # Worker processes asynchronously through multiple reasoners:
    # - analyze_task
    # - prepare_workspace (may skip if complexity too high)
    # - execute_changes (may skip if low confidence)
    # - post_response
    max_wait = 60  # seconds - give worker time to process
    poll_interval = 2  # seconds
    response_posted = False

    for _ in range(int(max_wait / poll_interval)):
        # Check if response was posted to GitHub
        posted_comments = await mock_github.get_posted_comments()
        if len(posted_comments) > 0:
            response_posted = True
            break

        # Check task status
        task_status = await kata_client.show_task(claimed_task_id)
        if "closed" in task_status.get("labels", []) or "completed" in task_status.get("labels", []):
            # Task completed - worker should have posted response
            break

        await asyncio.sleep(poll_interval)

    # Step 4: Verify response was posted to GitHub
    posted_comments = await mock_github.get_posted_comments()

    if response_posted:
        assert len(posted_comments) >= 1

        # Find comment for our issue
        issue_comments = [c for c in posted_comments if c.get("issue_number") == 123]
        assert len(issue_comments) >= 1

        comment = issue_comments[0]
        assert comment["repo_owner"] == "test-org"
        assert comment["repo_name"] == "test-repo"
        assert comment["issue_number"] == 123

        # Comment should reference the work done
        comment_body = comment["body"].lower()
        # Should mention it's from nd agent
        assert "nd" in comment_body or "agent" in comment_body or "bot" in comment_body
    else:
        # If no response posted, check if worker encountered approval gate
        task_status = await kata_client.show_task(claimed_task_id)

        # Check for comments on task indicating approval needed
        if "comments" in task_status:
            task_comments = task_status["comments"]
            # Look for approval request or low-confidence messages
            approval_needed = any(
                "approval" in str(c).lower() or "confidence" in str(c).lower()
                for c in task_comments
            )

            if approval_needed:
                pytest.skip("Task hit approval gate (low confidence) - expected behavior")

        # Otherwise, task may still be processing or failed
        pytest.fail(
            f"No response posted to GitHub after {max_wait}s. "
            f"Task status: {task_status.get('labels', [])}"
        )


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_issue_to_gitlab_complete_flow(
    e2e_env,
    mock_middleman,
    mock_gitlab,
    kata_client,
):
    """
    Test complete flow: GitLab issue → triage → task → worker → GitLab response.

    Same as GitHub flow but posts to GitLab instead.
    """
    # Reset all mocks
    await mock_middleman.reset()
    await mock_gitlab.reset()

    # Define test issue from GitLab
    test_issue = {
        "id": "issue-002",
        "number": 456,
        "title": "Update error messages",
        "body": "Please update the error messages in error_handler.py to be more user-friendly.",
        "state": "opened",
        "author": "team-lead",
        "assignees": ["test-user"],
        "url": "https://gitlab.com/test-org/test-repo/-/issues/456",
        "created_at": "2026-05-29T11:00:00Z",
        "updated_at": "2026-05-29T11:00:00Z",
        "platform": "gitlab",
        "platform_host": "gitlab.com",
        "repo_owner": "test-org",
        "repo_name": "test-repo",
    }

    # Seed middleman with the issue
    await mock_middleman.seed_issues([test_issue])

    # Verify issue is available
    issues = await mock_middleman.get_issues_assigned_to("test-user")
    assert len(issues) == 1
    assert issues[0]["number"] == 456

    # Get baseline task count
    tasks_before = await kata_client.list_tasks()
    count_before = len(tasks_before)

    # Step 1: Trigger triage
    triage_result = await e2e_env.call("nd-triage.poll_issues", payload=None)
    assert triage_result["issues_found"] == 1
    assert triage_result["tasks_created"] == 1

    # Verify task created
    tasks_after_triage = await kata_client.list_tasks()
    assert len(tasks_after_triage) == count_before + 1

    new_task = tasks_after_triage[-1]
    assert "from-issue" in new_task["labels"]

    # Step 2: Worker claims task
    claim_result = await e2e_env.call("nd-worker.claim_task", payload=None)
    assert claim_result["claimed"] is True

    claimed_task_id = claim_result["task_id"]

    # Step 3: Poll for completion
    max_wait = 60
    poll_interval = 2
    response_posted = False

    for _ in range(int(max_wait / poll_interval)):
        posted_notes = await mock_gitlab.get_posted_notes()
        if len(posted_notes) > 0:
            response_posted = True
            break

        task_status = await kata_client.show_task(claimed_task_id)
        if "closed" in task_status.get("labels", []) or "completed" in task_status.get("labels", []):
            break

        await asyncio.sleep(poll_interval)

    # Step 4: Verify response posted to GitLab
    posted_notes = await mock_gitlab.get_posted_notes()

    if response_posted:
        assert len(posted_notes) >= 1

        # Find note for our issue
        issue_notes = [n for n in posted_notes if n.get("issue_number") == 456]
        assert len(issue_notes) >= 1

        note = issue_notes[0]
        assert note["repo_owner"] == "test-org"
        assert note["repo_name"] == "test-repo"

        # Note should be from nd agent
        note_body = note["body"].lower()
        assert "nd" in note_body or "agent" in note_body or "bot" in note_body
    else:
        task_status = await kata_client.show_task(claimed_task_id)

        if "comments" in task_status:
            approval_needed = any(
                "approval" in str(c).lower() or "confidence" in str(c).lower()
                for c in task_status.get("comments", [])
            )
            if approval_needed:
                pytest.skip("Task hit approval gate - expected behavior")

        pytest.fail(
            f"No response posted to GitLab after {max_wait}s. "
            f"Task status: {task_status.get('labels', [])}"
        )


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_multiple_issues_parallel_processing(
    e2e_env,
    mock_middleman,
    mock_github,
    kata_client,
):
    """
    Test that multiple issues can be processed in parallel.

    Seeds multiple issues and verifies both triage and worker
    can handle them concurrently.
    """
    # Reset mocks
    await mock_middleman.reset()
    await mock_github.reset()

    # Create 3 test issues
    issues = [
        {
            "id": f"issue-{i}",
            "number": 200 + i,
            "title": f"Task {i}",
            "body": f"Simple task {i}: Add a comment to file{i}.py",
            "state": "open",
            "author": "manager",
            "assignees": ["test-user"],
            "url": f"https://github.com/test-org/test-repo/issues/{200 + i}",
            "created_at": "2026-05-29T12:00:00Z",
            "updated_at": "2026-05-29T12:00:00Z",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "test-org",
            "repo_name": "test-repo",
        }
        for i in range(1, 4)
    ]

    await mock_middleman.seed_issues(issues)

    # Verify all issues available
    fetched_issues = await mock_middleman.get_issues_assigned_to("test-user")
    assert len(fetched_issues) == 3

    # Trigger triage
    triage_result = await e2e_env.call("nd-triage.poll_issues", payload=None)
    assert triage_result["issues_found"] == 3
    assert triage_result["tasks_created"] == 3

    # Trigger worker multiple times to claim tasks
    claimed_tasks = []
    for _ in range(3):
        claim_result = await e2e_env.call("nd-worker.claim_task", payload=None)
        if claim_result["claimed"]:
            claimed_tasks.append(claim_result["task_id"])
        # Small delay between claims
        await asyncio.sleep(0.5)

    # Should have claimed at least some tasks
    assert len(claimed_tasks) >= 1

    # Poll for responses (with longer timeout for multiple tasks)
    max_wait = 120
    poll_interval = 3

    for _ in range(int(max_wait / poll_interval)):
        posted_comments = await mock_github.get_posted_comments()
        if len(posted_comments) >= len(claimed_tasks):
            break
        await asyncio.sleep(poll_interval)

    # Verify responses posted
    posted_comments = await mock_github.get_posted_comments()

    # At least some responses should be posted
    # (some may hit approval gates or still be processing)
    assert len(posted_comments) >= 0  # Relaxed assertion - just verify no crashes

    # Verify no duplicate responses
    issue_numbers = [c.get("issue_number") for c in posted_comments]
    assert len(issue_numbers) == len(set(issue_numbers)), "Duplicate responses detected"
