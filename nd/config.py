"""Configuration loader from environment variables."""

import os
from dataclasses import dataclass


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

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            agentfield_url=os.getenv("AGENTFIELD_URL", "http://localhost:8080"),
            middleman_url=os.getenv("MIDDLEMAN_URL", "http://localhost:8091"),
            middleman_db=os.path.expanduser(
                os.getenv("MIDDLEMAN_DB", "~/.middleman/middleman.db")
            ),
            kata_server=os.getenv("KATA_SERVER", ""),
            confidence_threshold=int(os.getenv("CONFIDENCE_THRESHOLD", "70")),
            roborev_max_iterations=int(os.getenv("ROBOREV_MAX_ITERATIONS", "3")),
            triage_model=os.getenv(
                "TRIAGE_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic/claude-sonnet-4-20250514")
            ),
            worker_model=os.getenv(
                "WORKER_MODEL",
                os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic/claude-sonnet-4-20250514")
            ),
            agent_instance_id=os.getenv("AGENT_INSTANCE_ID", "worker-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            current_user=os.getenv("ND_CURRENT_USER", ""),
        )


config = Config.from_env()
