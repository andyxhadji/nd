"""
E2E tests for mock services without requiring LLM calls.

These tests verify the E2E infrastructure works correctly.
"""

import os

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("SKIP_DOCKER_TESTS") == "true", reason="Docker compose not available")
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
