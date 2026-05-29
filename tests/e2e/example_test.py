"""
Example E2E test demonstrating the testing framework.

This file shows common patterns and best practices for writing E2E tests.
Run with: pytest tests/e2e/example_test.py -v
"""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_full_flow(
    e2e_env,
    mock_middleman,
    mock_github,
    kata_client,
):
    """
    Example: Complete flow from comment to response.

    This demonstrates:
    1. Seeding mock data
    2. Triggering agent reasoners
    3. Verifying task creation
    4. Checking mock service interactions
    """
    # Setup: Reset mocks and seed data
    await mock_middleman.reset()
    await mock_github.reset()

    comment = {
        "body": "Please add input validation to this function",
        "author": "code-reviewer",
        "mr_title": "Add new API endpoint",
        "mr_number": 42,
        "mr_url": "https://github.com/example-org/example-repo/pull/42",
        "head_branch": "feature/api-endpoint",
        "base_branch": "main",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "example-org",
        "repo_name": "example-repo",
        "dedupe_key": "example:test:unique-1",
    }

    await mock_middleman.seed_comments([comment])

    # Act: Trigger triage agent to poll and create task
    poll_result = await e2e_env.call("nd-triage.poll_comments", payload=None)

    # Assert: Verify triage behavior
    assert poll_result["comments_found"] == 1
    assert poll_result["tasks_created"] == 1
    assert len(poll_result.get("errors", [])) == 0

    # Verify task was created in kata with correct labels
    tasks = await kata_client.list_tasks(project="example-repo")
    assert len(tasks) >= 1

    task = tasks[-1]
    assert "nd" in task["labels"]
    assert "from-mr" in task["labels"]

    # Act: Trigger worker to claim the task
    claim_result = await e2e_env.call("nd-worker.claim_task", payload=None)

    # Assert: Verify worker claimed the task
    assert claim_result["claimed"] is True
    assert claim_result["task_id"] is not None
    assert claim_result["project"] == "example-repo"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_classification(e2e_env):
    """
    Example: Test classification of different comment types.

    This demonstrates testing a single reasoner in isolation.
    """
    # Test actionable request
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Can you add error handling here?",
        author="reviewer",
        mr_title="Feature implementation",
        mr_number=1,
    )

    assert result["actionable"] is True
    assert result["category"] in ["request", "feedback"]
    assert result["confident"] is True

    # Test non-actionable acknowledgment
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="LGTM! Great work!",
        author="reviewer",
        mr_title="Bug fix",
        mr_number=2,
    )

    assert result["actionable"] is False
    assert result["category"] == "acknowledgment"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_task_analysis(e2e_env):
    """
    Example: Test worker's task analysis.

    This demonstrates testing complexity estimation.
    """
    # Simple task - should have low complexity, high confidence
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Add a log statement at line 42",
        comment_category="request",
        mr_title="Add logging",
        head_branch="feature/logging",
        repo_path="/tmp/example-repo",
    )

    assert result["complexity"] <= 3
    assert result["confidence"] >= 60
    assert "files_likely_affected" in result

    # Complex task - should have high complexity, lower confidence
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Refactor the entire authentication system to use OAuth2 with PKCE",
        comment_category="request",
        mr_title="Auth refactor",
        head_branch="refactor/auth",
        repo_path="/tmp/example-repo",
    )

    assert result["complexity"] >= 4


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_fixture_loading(fixture_loader, mock_middleman):
    """
    Example: Using fixture files for test data.

    This demonstrates loading test data from JSON files.
    """
    # Load pre-defined comments
    comments = fixture_loader("comments.json")
    assert isinstance(comments, list)
    assert len(comments) > 0

    # Seed them into mock
    await mock_middleman.seed_comments(comments)

    # Verify they were seeded
    retrieved = await mock_middleman.get_comments()
    assert len(retrieved) == len(comments)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_scenario(scenario_loader, mock_middleman, e2e_env):
    """
    Example: Using scenario files for complex test cases.

    This demonstrates loading and executing a pre-defined scenario.
    """
    # Load scenario
    scenario = scenario_loader("simple_request.json")

    assert scenario["name"] == "Simple request flow"
    assert "initial_state" in scenario
    assert "expected_flow" in scenario

    # Setup initial state
    await mock_middleman.reset()
    await mock_middleman.seed_comments(scenario["initial_state"]["comments"])

    # Execute first step from scenario
    first_step = scenario["expected_flow"][0]
    if first_step["reasoner"] == "poll_comments":
        result = await e2e_env.call("nd-triage.poll_comments", payload=None)

        expected = first_step["expected_result"]
        assert result["comments_found"] == expected["comments_found"]
        assert result["tasks_created"] == expected["tasks_created"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_mock_verification(e2e_env, mock_github):
    """
    Example: Verifying interactions with mock services.

    This demonstrates checking what the agent posted to GitHub.
    """
    # In a real test, you'd trigger a workflow that posts to GitHub
    # For this example, we just verify the mock works

    # Reset mock
    await mock_github.reset()

    # Check no comments posted yet
    posted = await mock_github.get_posted_comments()
    assert len(posted) == 0

    # In real usage, agent would post here via platform client
    # posted = await mock_github.get_posted_comments()
    # assert len(posted) == 1
    # assert "addressed" in posted[0]["body"].lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_error_handling(e2e_env, mock_middleman):
    """
    Example: Testing error conditions.

    This demonstrates verifying error handling and edge cases.
    """
    # Test with empty comments
    await mock_middleman.reset()

    result = await e2e_env.call("nd-triage.poll_comments", payload=None)

    assert result["comments_found"] == 0
    assert result["tasks_created"] == 0
    assert len(result.get("errors", [])) == 0  # No errors on empty input


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_kata_operations(kata_client):
    """
    Example: Direct kata operations.

    This demonstrates creating and inspecting tasks in kata.
    """
    # Create a test task
    task_id = await kata_client.create_task(
        title="Example task for testing",
        body="This is a test task body",
        project="example-project",
        labels=["test", "nd"],
    )

    assert task_id is not None
    assert "#" in task_id  # Format: project#id

    # Retrieve task details
    task = await kata_client.show_task(task_id)

    assert task["title"] == "Example task for testing"
    assert "test" in task["labels"]
    assert "nd" in task["labels"]


# This test is marked to skip in CI but can run locally
@pytest.mark.e2e
@pytest.mark.skip_ci
@pytest.mark.asyncio
async def test_example_local_only(e2e_env):
    """
    Example: Local-only test.

    This demonstrates tests that shouldn't run in CI
    (e.g., require specific local setup, very slow, etc.)
    """
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Local test",
        author="dev",
        mr_title="Test",
        mr_number=999,
    )

    assert "actionable" in result
