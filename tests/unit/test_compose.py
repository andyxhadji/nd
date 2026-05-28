"""Regression checks for docker compose wiring."""

from pathlib import Path


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
