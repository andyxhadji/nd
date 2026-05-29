"""
E2E tests for mock services without requiring LLM calls.

These tests verify the E2E infrastructure works correctly.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mock_middleman_seed_and_query(mock_middleman):
    """Test that we can seed and query mock middleman."""
    # Reset first
    await mock_middleman.reset()

    # Seed a comment
    comment = {
        "body": "Test comment for E2E",
        "author": "test-reviewer",
        "mr_title": "Test MR",
        "mr_number": 100,
        "mr_url": "https://github.com/test/repo/pull/100",
        "head_branch": "test-branch",
        "base_branch": "main",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "test",
        "repo_name": "repo",
        "dedupe_key": "test:e2e:mock:1",
    }

    await mock_middleman.seed_comments([comment])

    # Query it back
    comments = await mock_middleman.get_comments()

    assert len(comments) == 1
    assert comments[0]["body"] == "Test comment for E2E"
    assert comments[0]["author"] == "test-reviewer"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2E docker-compose services running")
async def test_mock_middleman_user_filtering(mock_middleman):
    """Test that mock middleman filters by current_user."""
    await mock_middleman.reset()

    # Seed multiple comments
    comments = [
        {
            "body": "Comment from user A",
            "author": "user-a",
            "mr_title": "Test",
            "mr_number": 1,
            "mr_url": "https://github.com/test/repo/pull/1",
            "head_branch": "test",
            "base_branch": "main",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "test",
            "repo_name": "repo",
            "dedupe_key": "test:1",
        },
        {
            "body": "Comment from user B",
            "author": "user-b",
            "mr_title": "Test",
            "mr_number": 2,
            "mr_url": "https://github.com/test/repo/pull/2",
            "head_branch": "test",
            "base_branch": "main",
            "platform": "github",
            "platform_host": "github.com",
            "repo_owner": "test",
            "repo_name": "repo",
            "dedupe_key": "test:2",
        },
    ]

    await mock_middleman.seed_comments(comments)

    # Query all - should get 2
    all_comments = await mock_middleman.get_comments()
    assert len(all_comments) == 2

    # Query filtering current_user=user-a - should exclude user-a's comments
    filtered = await mock_middleman.get_comments(current_user="user-a")
    assert len(filtered) == 1
    assert filtered[0]["author"] == "user-b"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2E docker-compose services running")
async def test_mock_middleman_issues(mock_middleman):
    """Test that we can seed and query issues."""
    await mock_middleman.reset()

    issue = {
        "number": 200,
        "title": "Test issue",
        "body": "This is a test issue",
        "url": "https://github.com/test/repo/issues/200",
        "author": "issue-author",
        "assignees": ["assignee1", "assignee2"],
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "test",
        "repo_name": "repo",
    }

    await mock_middleman.seed_issues([issue])

    # Query by assignee
    issues = await mock_middleman.get_issues_assigned_to("assignee1")
    assert len(issues) == 1
    assert issues[0]["title"] == "Test issue"

    issues = await mock_middleman.get_issues_assigned_to("assignee2")
    assert len(issues) == 1

    issues = await mock_middleman.get_issues_assigned_to("other-user")
    assert len(issues) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2E docker-compose services running")
async def test_mock_github_captures_posts(mock_github):
    """Test that mock GitHub captures posted comments."""
    await mock_github.reset()

    # Initially no posts
    posts = await mock_github.get_posted_comments()
    assert len(posts) == 0

    # In a real test, the agent would post here
    # For now we just verify the mock works


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2E docker-compose services running")
async def test_mock_gitlab_captures_notes(mock_gitlab):
    """Test that mock GitLab captures posted notes."""
    await mock_gitlab.reset()

    # Initially no notes
    notes = await mock_gitlab.get_posted_notes()
    assert len(notes) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2E docker-compose services running")
async def test_kata_client_operations(kata_client):
    """Test kata client can list and show tasks."""
    # Note: kata requires a project to be initialized. In the E2E environment,
    # projects are created on-demand by the agents. We test with a project name.
    try:
        tasks = await kata_client.list_tasks(project="test-repo")
        assert isinstance(tasks, list)
    except RuntimeError as e:
        # If kata reports project not initialized, that's expected in a fresh env
        if "not_found" in str(e) or "project_not_initialized" in str(e):
            pytest.skip("Kata project not initialized - expected in fresh E2E environment")
        raise

    # Note: We don't create tasks here since that would persist
    # across test runs. Real E2E tests will create and verify.


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fixture_and_scenario_loading(fixture_loader, scenario_loader):
    """Test that fixtures and scenarios load correctly in E2E env."""
    # Load comments fixture
    comments = fixture_loader("comments.json")
    assert isinstance(comments, list)
    assert len(comments) > 0

    # Load issues fixture
    issues = fixture_loader("issues.json")
    assert isinstance(issues, list)
    assert len(issues) > 0

    # Load scenario
    scenario = scenario_loader("simple_request.json")
    assert isinstance(scenario, dict)
    assert "name" in scenario
    assert "initial_state" in scenario


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_e2e_environment_ready(e2e_env):
    """Test that E2E environment is properly initialized."""
    # Verify we have an environment controller
    assert e2e_env is not None
    assert hasattr(e2e_env, "agent")
    assert hasattr(e2e_env, "call")
    assert hasattr(e2e_env, "service_urls")

    # Verify service URLs are configured
    urls = e2e_env.service_urls
    assert "agentfield" in urls
    assert "middleman" in urls
    assert "github" in urls
    assert "gitlab" in urls
