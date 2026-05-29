"""E2E tests for triage agent in isolation."""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_classify_actionable_request(e2e_env):
    """Test classification of an actionable request."""
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Can you add error handling here?",
        author="reviewer",
        mr_title="Add feature",
        mr_number=42,
    )

    assert result["actionable"] is True
    assert result["category"] in ["request", "feedback"]
    assert result["reason"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_classify_non_actionable_lgtm(e2e_env):
    """Test classification of non-actionable LGTM comment."""
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="LGTM",
        author="reviewer",
        mr_title="Add feature",
        mr_number=42,
    )

    assert result["actionable"] is False
    assert result["category"] == "acknowledgment"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_classify_question(e2e_env):
    """Test classification of a question."""
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Why did you use approach X instead of Y?",
        author="reviewer",
        mr_title="Refactor module",
        mr_number=10,
    )

    assert result["actionable"] is True
    assert result["category"] == "question"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_classify_bot_comment(e2e_env):
    """Test classification of bot comments."""
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="Coverage decreased by 2%",
        author="codecov[bot]",
        mr_title="Add tests",
        mr_number=20,
    )

    assert result["actionable"] is False
    assert result["category"] == "bot"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_task_from_comment(
    e2e_env,
    kata_client,
):
    """Test task creation from a valid comment."""
    # Get baseline
    tasks_before = await kata_client.list_tasks()
    count_before = len(tasks_before)

    result = await e2e_env.call(
        "nd-triage.create_task",
        comment_body="Please add validation here",
        comment_author="reviewer",
        comment_dedupe_key="test:e2e:unique-key-1",
        mr_number=42,
        mr_title="Add validation",
        mr_url="https://github.com/test-org/test-repo/pull/42",
        head_branch="feature/validation",
        base_branch="main",
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
        classification={
            "actionable": True,
            "reason": "Request to add validation",
            "category": "request",
            "confident": True,
        },
    )

    assert result["created"] is True
    assert result["task_id"] is not None

    # Verify task exists
    tasks_after = await kata_client.list_tasks()
    assert len(tasks_after) == count_before + 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_task_duplicate_detection(e2e_env, kata_client):
    """Test that duplicate task creation is prevented."""
    dedupe_key = "test:e2e:duplicate-test"

    # Create first task
    result1 = await e2e_env.call(
        "nd-triage.create_task",
        comment_body="Fix this bug",
        comment_author="reviewer",
        comment_dedupe_key=dedupe_key,
        mr_number=99,
        mr_title="Bug fix",
        mr_url="https://github.com/test-org/test-repo/pull/99",
        head_branch="fix/bug",
        base_branch="main",
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
        classification={
            "actionable": True,
            "reason": "Bug fix request",
            "category": "request",
            "confident": True,
        },
    )

    assert result1["created"] is True

    # Try to create duplicate
    result2 = await e2e_env.call(
        "nd-triage.create_task",
        comment_body="Fix this bug",
        comment_author="reviewer",
        comment_dedupe_key=dedupe_key,
        mr_number=99,
        mr_title="Bug fix",
        mr_url="https://github.com/test-org/test-repo/pull/99",
        head_branch="fix/bug",
        base_branch="main",
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
        classification={
            "actionable": True,
            "reason": "Bug fix request",
            "category": "request",
            "confident": True,
        },
    )

    assert result2["created"] is False
    assert result2["skipped_reason"] == "duplicate"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_issue_task(e2e_env, kata_client):
    """Test task creation from an issue."""
    # Get baseline
    tasks_before = await kata_client.list_tasks()
    count_before = len(tasks_before)

    result = await e2e_env.call(
        "nd-triage.create_issue_task",
        issue_number=150,
        issue_title="Improve error messages",
        issue_body="Error messages are too generic. Make them more specific.",
        issue_url="https://github.com/test-org/test-repo/issues/150",
        issue_author="user1",
        assignees=["test-user"],
        platform="github",
        platform_host="github.com",
        repo_owner="test-org",
        repo_name="test-repo",
    )

    assert result["created"] is True
    assert result["task_id"] is not None

    # Verify task has from-issue label
    tasks_after = await kata_client.list_tasks()
    assert len(tasks_after) == count_before + 1

    task = tasks_after[-1]
    assert "from-issue" in task["labels"]
    assert "nd" in task["labels"]
