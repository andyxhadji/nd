# tests/unit/test_config.py
"""Unit tests for nd.config."""

import importlib

import nd.config as config_module
from nd.config import Config, _parse_usernames


class TestParseUsernames:
    def test_empty_string(self):
        assert _parse_usernames("") == []

    def test_single(self):
        assert _parse_usernames("alice") == ["alice"]

    def test_multiple(self):
        assert _parse_usernames("alice,bob,carol") == ["alice", "bob", "carol"]

    def test_strips_whitespace(self):
        assert _parse_usernames(" alice , bob ,  carol  ") == ["alice", "bob", "carol"]

    def test_drops_empty_entries(self):
        assert _parse_usernames("alice,,bob,") == ["alice", "bob"]

    def test_only_separators(self):
        assert _parse_usernames(",,,") == []


class TestConfigFromEnv:
    def test_defaults(self, monkeypatch):
        # Clear all env vars the config reads so we exercise the defaults branch
        for var in [
            "AGENTFIELD_URL",
            "MIDDLEMAN_URL",
            "MIDDLEMAN_DB",
            "KATA_SERVER",
            "CONFIDENCE_THRESHOLD",
            "ROBOREV_MAX_ITERATIONS",
            "TRIAGE_MODEL",
            "WORKER_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "AGENT_INSTANCE_ID",
            "GITHUB_TOKEN",
            "GITLAB_TOKEN",
            "ND_CURRENT_USER",
            "ND_ASSIGNED_USERNAMES",
        ]:
            monkeypatch.delenv(var, raising=False)

        cfg = Config.from_env()
        assert cfg.agentfield_url == "http://localhost:8080"
        assert cfg.middleman_url == "http://localhost:8091"
        assert cfg.middleman_db.endswith("/.middleman/middleman.db")
        assert cfg.kata_server == ""
        assert cfg.confidence_threshold == 70
        assert cfg.roborev_max_iterations == 3
        assert cfg.triage_model == "anthropic/claude-sonnet-4-20250514"
        assert cfg.worker_model == "anthropic/claude-sonnet-4-20250514"
        assert cfg.agent_instance_id == "worker-1"
        assert cfg.github_token == ""
        assert cfg.gitlab_token == ""
        assert cfg.current_user == ""
        assert cfg.assigned_usernames == []

    def test_overrides(self, monkeypatch):
        monkeypatch.setenv("AGENTFIELD_URL", "http://af:9000")
        monkeypatch.setenv("MIDDLEMAN_URL", "http://mm:9001")
        monkeypatch.setenv("MIDDLEMAN_DB", "/tmp/mm.db")
        monkeypatch.setenv("KATA_SERVER", "kata.local:7000")
        monkeypatch.setenv("CONFIDENCE_THRESHOLD", "85")
        monkeypatch.setenv("ROBOREV_MAX_ITERATIONS", "7")
        monkeypatch.setenv("TRIAGE_MODEL", "anthropic/claude-opus")
        monkeypatch.setenv("WORKER_MODEL", "anthropic/claude-haiku")
        monkeypatch.setenv("AGENT_INSTANCE_ID", "worker-42")
        monkeypatch.setenv("GITHUB_TOKEN", "gh-token")
        monkeypatch.setenv("GITLAB_TOKEN", "gl-token")
        monkeypatch.setenv("ND_CURRENT_USER", "alice")
        monkeypatch.setenv("ND_ASSIGNED_USERNAMES", "alice,bob")

        cfg = Config.from_env()
        assert cfg.agentfield_url == "http://af:9000"
        assert cfg.middleman_url == "http://mm:9001"
        assert cfg.middleman_db == "/tmp/mm.db"
        assert cfg.kata_server == "kata.local:7000"
        assert cfg.confidence_threshold == 85
        assert cfg.roborev_max_iterations == 7
        assert cfg.triage_model == "anthropic/claude-opus"
        assert cfg.worker_model == "anthropic/claude-haiku"
        assert cfg.agent_instance_id == "worker-42"
        assert cfg.github_token == "gh-token"
        assert cfg.gitlab_token == "gl-token"
        assert cfg.current_user == "alice"
        assert cfg.assigned_usernames == ["alice", "bob"]

    def test_model_falls_back_to_anthropic_default(self, monkeypatch):
        monkeypatch.delenv("TRIAGE_MODEL", raising=False)
        monkeypatch.delenv("WORKER_MODEL", raising=False)
        monkeypatch.setenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "anthropic/claude-test")

        cfg = Config.from_env()
        assert cfg.triage_model == "anthropic/claude-test"
        assert cfg.worker_model == "anthropic/claude-test"

    def test_module_level_config_singleton_exists(self):
        # Cover the module-level `config = Config.from_env()` line
        assert isinstance(config_module.config, Config)

    def test_middleman_db_expands_user(self, monkeypatch):
        monkeypatch.setenv("MIDDLEMAN_DB", "~/custom.db")
        cfg = Config.from_env()
        assert not cfg.middleman_db.startswith("~")
        assert cfg.middleman_db.endswith("/custom.db")

    def test_reload_reflects_env_changes(self, monkeypatch):
        # Ensure module reload picks up new env (sanity test for dev workflows)
        monkeypatch.setenv("ND_CURRENT_USER", "reload-user")
        importlib.reload(config_module)
        try:
            assert config_module.config.current_user == "reload-user"
        finally:
            # Restore module-level config to a clean state for other tests
            importlib.reload(config_module)
