"""E2E tests for worker agent in isolation."""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_analyze_simple_task(e2e_env):
    """Test analysis of a simple, low-complexity task."""
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Add a log statement at line 42",
        comment_category="request",
        mr_title="Add logging",
        head_branch="feature/logging",
        repo_path="/tmp/test-repo",  # Dummy path for analysis
    )

    assert "complexity" in result
    assert "confidence" in result
    assert result["complexity"] <= 3
    assert result["confidence"] >= 60


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_analyze_complex_task(e2e_env):
    """Test analysis of a complex, high-complexity task."""
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Refactor the entire authentication module to use OAuth2 with PKCE flow and add comprehensive test coverage",
        comment_category="request",
        mr_title="Refactor auth",
        head_branch="refactor/auth",
        repo_path="/tmp/test-repo",
    )

    assert "complexity" in result
    assert "confidence" in result
    assert result["complexity"] >= 4  # Should be high complexity
    # Confidence may vary, but should return a value


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_analyze_question(e2e_env):
    """Test analysis of a question (not a request)."""
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Why did you choose this implementation?",
        comment_category="question",
        mr_title="Implementation question",
        head_branch="main",
        repo_path="/tmp/test-repo",
    )

    assert "complexity" in result
    assert "confidence" in result
    # Questions typically have low confidence since they need human response
    assert result["confidence"] < 70


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_draft_response_simple(e2e_env):
    """Test response drafting for a simple change."""
    result = await e2e_env.call(
        "nd-worker.draft_response",
        comment_body="Add error handling",
        changes_made=["src/main.py", "tests/test_main.py"],
        commit_sha="abc123def456",
    )

    assert "response_text" in result
    assert result["response_text"] != ""
    assert "abc123" in result["response_text"]  # Should mention commit
    assert "confident" in result


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_claim_task_when_available(e2e_env, kata_client):
    """Test claiming a task when one is available."""
    # Create a task
    await kata_client.create_task(
        title="Test task for claiming",
        body="This is a test task",
        project="test-repo",
        labels=["nd"],
    )

    # Claim it
    result = await e2e_env.call("nd-worker.claim_task", payload=None)

    # Should either claim this task or another available one
    assert "claimed" in result
    if result["claimed"]:
        assert result["task_id"] is not None
        assert result["project"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires E2EEnvironment agent registration (tracked separately)")
async def test_workspace_cleanup(e2e_env):
    """Test workspace cleanup reasoner."""
    # This is a unit-style test but runs against real agent
    result = await e2e_env.call(
        "nd-worker.cleanup_workspace",
        repo_path="/tmp/nonexistent-path",
        bare_path="/tmp/nonexistent-bare",
        branch="test-branch",
    )

    # Should return cleaned status (even if path doesn't exist)
    assert "cleaned" in result
    assert isinstance(result["cleaned"], bool)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires actual git repository setup")
async def test_prepare_workspace_mr_task(e2e_env):
    """
    Test workspace preparation for an MR task.

    This requires a real git repository to be available.
    Skip by default; enable when testing against real repos.
    """
    result = await e2e_env.call(
        "nd-worker.prepare_workspace",
        task_id="test-task-1",
        project="test-repo",
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
        head_branch="main",
        base_branch="main",
        is_issue=False,
    )

    assert "prepared" in result
    if result["prepared"]:
        assert result["repo_path"] is not None
        assert result["branch"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires actual git repository setup")
async def test_prepare_workspace_issue_task(e2e_env):
    """
    Test workspace preparation for an issue task (creates new branch).

    This requires a real git repository to be available.
    Skip by default; enable when testing against real repos.
    """
    result = await e2e_env.call(
        "nd-worker.prepare_workspace",
        task_id="test-repo#123",
        project="test-repo",
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
        base_branch="main",
        is_issue=True,
        issue_short_id="123",
    )

    assert "prepared" in result
    if result["prepared"]:
        assert result["repo_path"] is not None
        assert result["branch"] is not None
        assert result["branch"].startswith("nd/issue-")
