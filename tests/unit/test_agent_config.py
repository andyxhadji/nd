"""Regression checks for agent AI configuration."""

from types import SimpleNamespace

from nd.triage import agent as triage_agent
from nd.worker import agent as worker_agent


def test_triage_agent_omits_temperature_for_bedrock_claude_4(monkeypatch) -> None:
    monkeypatch.setattr(
        triage_agent,
        "config",
        SimpleNamespace(
            triage_model="bedrock/converse/test-opus-profile",
            agentfield_url="http://agentfield",
            middleman_url="http://middleman",
            kata_server="",
            current_user="alice",
            assigned_usernames=[],
        ),
    )

    app = triage_agent.create_triage_agent(node_id="triage-config-test")

    assert app.ai_config.model == "bedrock/converse/test-opus-profile"
    assert app.ai_config.temperature is None


def test_worker_agent_omits_temperature_for_bedrock_claude_4(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_agent,
        "config",
        SimpleNamespace(
            worker_model="bedrock/converse/test-opus-profile",
            agentfield_url="http://agentfield",
            kata_server="",
            github_token="",
            gitlab_token="",
            workspace_root="/tmp/nd-test",
        ),
    )

    app = worker_agent.create_worker_agent(node_id="worker-config-test")

    assert app.ai_config.model == "bedrock/converse/test-opus-profile"
    assert app.ai_config.temperature is None
