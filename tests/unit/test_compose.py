"""Regression checks for docker compose wiring."""

from pathlib import Path

OPUS_PROFILE = "mj2ayeqbysnr"
SONNET_PROFILE = "fa9v3zo70aog"


def _service_block(compose_text: str, service_name: str) -> str:
    start = compose_text.index(f"  {service_name}:\n")
    next_service = compose_text.find("\n  ", start + 1)
    while next_service != -1 and compose_text[next_service + 3] == " ":
        next_service = compose_text.find("\n  ", next_service + 1)
    return compose_text[start:] if next_service == -1 else compose_text[start:next_service]


def test_workers_bind_mount_host_workspace_to_var_nd() -> None:
    compose = Path("docker-compose.yml").read_text()

    for service_name in ("worker-1", "worker-2"):
        block = _service_block(compose, service_name)

        assert "volumes:" in block
        assert "- ${ND_WORKSPACE_ROOT:-./.nd-workspace}:/var/nd" in block


def test_agent_model_defaults_use_claude_code_opus_profile() -> None:
    compose = Path("docker-compose.yml").read_text()

    for service_name, env_name in (
        ("triage", "TRIAGE_MODEL"),
        ("worker-1", "WORKER_MODEL"),
        ("worker-2", "WORKER_MODEL"),
    ):
        block = _service_block(compose, service_name)

        assert f"{env_name}=${{{env_name}:-bedrock/converse/" in block
        assert OPUS_PROFILE in block
        assert SONNET_PROFILE not in block
