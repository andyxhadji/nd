"""Packaging regression checks for runtime dependencies."""

import tomllib
from pathlib import Path


def test_claude_agent_sdk_is_runtime_dependency() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]

    assert "claude-agent-sdk>=0.2.87" in project["dependencies"]


def test_worker_compose_mounts_claude_code_auth() -> None:
    compose = Path("docker-compose.yml").read_text()

    assert "${HOME}/.claude:/root/.claude" in compose
    assert "${HOME}/.claude.json:/root/.claude.json" in compose


def test_worker_compose_configures_claude_code_bedrock() -> None:
    compose = Path("docker-compose.yml").read_text()

    assert "CLAUDE_CODE_USE_BEDROCK=${CLAUDE_CODE_USE_BEDROCK:-1}" in compose
    assert "AWS_REGION=${AWS_REGION:-us-east-1}" in compose
    assert (
        "ANTHROPIC_MODEL=${CLAUDE_CODE_MODEL:-arn:aws:bedrock:us-east-1:657062785455:"
        "application-inference-profile/mj2ayeqbysnr}"
    ) in compose
    assert "CLAUDE_CODE_MAX_OUTPUT_TOKENS=${CLAUDE_CODE_MAX_OUTPUT_TOKENS:-4096}" in compose


def test_full_worker_smoke_is_local_only() -> None:
    smoke_test = Path("tests/local/test_full_worker_smoke.py")
    source = smoke_test.read_text()

    assert "ND_RUN_FULL_WORKER_SMOKE" in source
    assert "pytest.skip" in source
    assert "docker compose" in source
