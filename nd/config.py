"""Configuration loader from environment variables."""

import os
from dataclasses import dataclass


def _parse_usernames(value: str) -> list[str]:
    """Parse comma-separated usernames into a list."""
    return [u.strip() for u in value.split(",") if u.strip()]


@dataclass(frozen=True)
class Config:
    """Application configuration from environment."""

    agentfield_url: str
    middleman_url: str
    middleman_db: str
    kata_server: str
    confidence_threshold: int
    roborev_max_iterations: int
    triage_model: str
    worker_model: str
    agent_instance_id: str
    github_token: str
    gitlab_token: str
    current_user: str
    assigned_usernames: list[str]
    agent_port: int
    workspace_root: str
    workspace_keep_on_failure: bool
    roborev_container_name: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            agentfield_url=os.getenv("AGENTFIELD_URL", "http://localhost:8080"),
            middleman_url=os.getenv("MIDDLEMAN_URL", "http://localhost:8091"),
            middleman_db=os.path.expanduser(os.getenv("MIDDLEMAN_DB", "~/.middleman/middleman.db")),
            kata_server=os.getenv("KATA_SERVER", ""),
            confidence_threshold=int(os.getenv("CONFIDENCE_THRESHOLD", "70")),
            roborev_max_iterations=int(os.getenv("ROBOREV_MAX_ITERATIONS", "3")),
            triage_model=os.getenv(
                "TRIAGE_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "anthropic/claude-opus-4-20250514"),
            ),
            worker_model=os.getenv(
                "WORKER_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", "anthropic/claude-opus-4-20250514"),
            ),
            agent_instance_id=os.getenv("AGENT_INSTANCE_ID", "worker-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            current_user=os.getenv("ND_CURRENT_USER", ""),
            assigned_usernames=_parse_usernames(os.getenv("ND_ASSIGNED_USERNAMES", "")),
            agent_port=int(os.getenv("AGENT_PORT", "0")),
            workspace_root=os.getenv("WORKSPACE_ROOT", "/var/nd"),
            workspace_keep_on_failure=os.getenv("WORKSPACE_KEEP_ON_FAILURE", "1")
            not in ("0", "false", "False", ""),
            roborev_container_name=os.getenv("ROBOREV_CONTAINER_NAME", "hyper-furniture-roborev-1"),
        )


config = Config.from_env()
