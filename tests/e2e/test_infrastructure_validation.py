"""Validate E2E test infrastructure without full agent flows.

These tests check that the basic E2E components work before attempting
full agent integration tests.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mock_services_reachable(service_urls):
    """Test that all mock services are reachable via HTTP."""
    import httpx

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Test mock middleman
        resp = await client.get(f"{service_urls['middleman']}/health")
        assert resp.status_code == 200, f"Mock middleman not healthy: {resp.status_code}"

        # Test mock GitHub
        resp = await client.get(f"{service_urls['github']}/health")
        assert resp.status_code == 200, f"Mock GitHub not healthy: {resp.status_code}"

        # Test mock GitLab
        resp = await client.get(f"{service_urls['gitlab']}/health")
        assert resp.status_code == 200, f"Mock GitLab not healthy: {resp.status_code}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mock_middleman_basic_operations(mock_middleman):
    """Test mock middleman basic seed/query without agents."""
    # Reset
    await mock_middleman.reset()

    # Seed a simple issue
    test_issue = {
        "id": "test-1",
        "number": 1,
        "title": "Test issue",
        "body": "Test body",
        "state": "open",
        "author": "tester",
        "assignees": ["test-user"],
        "url": "https://github.com/test/repo/issues/1",
        "created_at": "2026-05-29T10:00:00Z",
        "updated_at": "2026-05-29T10:00:00Z",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "test",
        "repo_name": "repo",
    }

    await mock_middleman.seed_issues([test_issue])

    # Query it back
    issues = await mock_middleman.get_issues_assigned_to("test-user")
    assert len(issues) == 1
    assert issues[0]["number"] == 1
    assert issues[0]["title"] == "Test issue"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Kata command interface needs investigation")
async def test_kata_client_basic_operations(kata_client):
    """Test kata client can interact with kata daemon."""
    # Ensure project is initialized
    await kata_client.ensure_project_initialized("test-infra")

    # List tasks (may be empty)
    tasks = await kata_client.list_tasks()
    assert isinstance(tasks, list)

    # Show count before creating
    count_before = len(tasks)

    # Create a test task
    task_ref = await kata_client.create_task(
        title="E2E Infrastructure Test Task",
        body="This is a test task to validate E2E infrastructure",
        project="test-infra",
        labels=["test", "e2e-validation"],
    )

    assert task_ref is not None
    assert "test-infra" in task_ref

    # Verify task was created
    tasks_after = await kata_client.list_tasks()
    assert len(tasks_after) == count_before + 1

    # Show the task
    task_detail = await kata_client.show_task(task_ref)
    assert task_detail["title"] == "E2E Infrastructure Test Task"
    assert "test" in task_detail["labels"]
    assert "e2e-validation" in task_detail["labels"]
