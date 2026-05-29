"""Test agent registration and e2e_env.call() functionality."""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_environment_agent_startup(e2e_env):
    """Test that E2E environment can start and register a test controller agent."""
    # This test validates the agent registration mechanism works
    # by ensuring the agent is started when we try to use e2e_env.call()

    # The agent should start on first call
    await e2e_env.ensure_agent_started()

    # Verify agent was created
    assert e2e_env._agent is not None
    assert e2e_env._agent.node_id == "e2e-test-controller"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skip(reason="Test agent.call() - may need debugging if agent registration has issues")
async def test_simple_reasoner_call(e2e_env):
    """Test calling a simple reasoner through agent.call()."""
    # Try calling a simple worker reasoner that doesn't require much setup
    try:
        result = await e2e_env.call(
            "nd-worker.analyze_task",
            comment_body="Add a log statement",
            comment_category="request",
            mr_title="Test MR",
            head_branch="test",
            repo_path="/tmp/test",
        )

        # Should return analysis result
        assert "complexity" in result
        assert "confidence" in result
    except Exception as e:
        pytest.fail(f"Agent call failed: {e}")
