"""Shared E2E test fixtures and configuration."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from agentfield import Agent, AIConfig


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--use-running-agent",
        action="store_true",
        default=False,
        help="Test against running docker-compose instead of E2E compose",
    )
    parser.addoption(
        "--e2e-timeout",
        type=int,
        default=300,
        help="Timeout for E2E tests in seconds",
    )


@pytest.fixture(scope="session")
def use_running_agent(request) -> bool:
    """Whether to use running agent from main docker-compose."""
    return request.config.getoption("--use-running-agent")


@pytest.fixture(scope="session")
def e2e_timeout(request) -> int:
    """Timeout for E2E operations."""
    return request.config.getoption("--e2e-timeout")


@pytest.fixture(scope="session")
def compose_file(use_running_agent) -> str:
    """Return the appropriate docker-compose file."""
    if use_running_agent:
        return "docker-compose.yml"
    return "tests/e2e/docker-compose.e2e.yml"


@pytest.fixture(scope="session")
def service_urls(use_running_agent) -> dict[str, str]:
    """Service URLs for the test environment."""
    if use_running_agent:
        # Main docker-compose uses different ports
        return {
            "agentfield": "http://localhost:8081",
            "middleman": "http://localhost:8091",
            "github": "http://localhost:8092",
            "gitlab": "http://localhost:8093",
        }
    return {
        "agentfield": "http://localhost:8080",
        "middleman": "http://localhost:8091",
        "github": "http://localhost:8092",
        "gitlab": "http://localhost:8093",
    }


@pytest.fixture(scope="session")
async def e2e_env(compose_file, service_urls, e2e_timeout, use_running_agent):
    """
    Start docker-compose environment for E2E tests.

    If --use-running-agent is set, assumes services are already running.
    Otherwise starts the E2E compose environment.
    """
    if not use_running_agent:
        # Start E2E compose
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            compose_file,
            "up",
            "-d",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if proc.returncode != 0:
            pytest.fail("Failed to start E2E docker-compose environment")

    # Wait for services to be healthy
    await _wait_for_services(service_urls, timeout=e2e_timeout)

    # Return environment controller
    env = E2EEnvironment(service_urls, compose_file)

    yield env

    # Cleanup if we started compose
    if not use_running_agent:
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            compose_file,
            "down",
            "-v",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


async def _wait_for_services(service_urls: dict[str, str], timeout: int):
    """Wait for all services to be healthy."""
    async with httpx.AsyncClient() as client:
        start = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start) < timeout:
            all_ready = True

            for name, url in service_urls.items():
                try:
                    resp = await client.get(f"{url}/health", timeout=2.0)
                    if resp.status_code != 200:
                        all_ready = False
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    all_ready = False
                    break

            if all_ready:
                return

            await asyncio.sleep(1)

        pytest.fail(f"Services did not become healthy within {timeout}s")


class E2EEnvironment:
    """Controller for E2E environment."""

    def __init__(self, service_urls: dict[str, str], compose_file: str):
        self.service_urls = service_urls
        self.compose_file = compose_file
        self._agent: Agent | None = None

    @property
    def agent(self) -> Agent:
        """Get or create agent for making cross-agent calls."""
        if self._agent is None:
            self._agent = Agent(
                node_id="e2e-test-controller",
                version="1.0.0",
                agentfield_server=self.service_urls["agentfield"],
                ai_config=AIConfig(
                    model=os.getenv(
                        "WORKER_MODEL",
                        "bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/mj2ayeqbysnr",
                    )
                ),
            )
        return self._agent

    async def call(self, reasoner: str, **kwargs) -> dict[str, Any]:
        """Call a reasoner in one of the running agents."""
        return await self.agent.call(reasoner, **kwargs)

    async def exec(self, service: str, cmd: list[str]) -> tuple[int, str, str]:
        """Execute a command in a docker-compose service."""
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            self.compose_file,
            "exec",
            "-T",
            service,
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )

    async def logs(self, service: str, tail: int = 50) -> str:
        """Get logs from a service."""
        proc = await asyncio.create_subprocess_exec(
            "docker-compose",
            "-f",
            self.compose_file,
            "logs",
            "--tail",
            str(tail),
            service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode() if stdout else ""


@pytest.fixture
async def mock_middleman(service_urls):
    """HTTP client for mock middleman service."""
    client = MockMiddlemanClient(service_urls["middleman"])
    yield client
    await client.close()


@pytest.fixture
async def mock_github(service_urls):
    """HTTP client for mock GitHub service."""
    client = MockGitHubClient(service_urls["github"])
    yield client
    await client.close()


@pytest.fixture
async def mock_gitlab(service_urls):
    """HTTP client for mock GitLab service."""
    client = MockGitLabClient(service_urls["gitlab"])
    yield client
    await client.close()


class MockMiddlemanClient:
    """Client for interacting with mock middleman service."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def seed_comments(self, comments: list[dict]) -> None:
        """Seed mock middleman with comments."""
        resp = await self.client.post("/seed/comments", json=comments)
        resp.raise_for_status()

    async def seed_issues(self, issues: list[dict]) -> None:
        """Seed mock middleman with issues."""
        resp = await self.client.post("/seed/issues", json=issues)
        resp.raise_for_status()

    async def get_comments(
        self, since: str | None = None, current_user: str | None = None
    ) -> list[dict]:
        """Get comments from mock middleman."""
        params = {}
        if since:
            params["since"] = since
        if current_user:
            params["current_user"] = current_user

        resp = await self.client.get("/comments", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_issues_assigned_to(self, username: str) -> list[dict]:
        """Get issues assigned to a user."""
        resp = await self.client.get(f"/issues/assigned/{username}")
        resp.raise_for_status()
        return resp.json()

    async def reset(self) -> None:
        """Clear all mock data."""
        resp = await self.client.post("/reset")
        resp.raise_for_status()


class MockGitHubClient:
    """Client for interacting with mock GitHub service."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def get_posted_comments(self) -> list[dict]:
        """Get all comments that were posted to mock GitHub."""
        resp = await self.client.get("/verify")
        resp.raise_for_status()
        return resp.json()

    async def reset(self) -> None:
        """Clear all mock data."""
        resp = await self.client.post("/reset")
        resp.raise_for_status()


class MockGitLabClient:
    """Client for interacting with mock GitLab service."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def get_posted_notes(self) -> list[dict]:
        """Get all notes that were posted to mock GitLab."""
        resp = await self.client.get("/verify")
        resp.raise_for_status()
        return resp.json()

    async def reset(self) -> None:
        """Clear all mock data."""
        resp = await self.client.post("/reset")
        resp.raise_for_status()


@pytest.fixture
async def kata_client(e2e_env):
    """Client for kata daemon."""
    return KataTestClient(e2e_env)


class KataTestClient:
    """Test client for kata daemon."""

    def __init__(self, env: E2EEnvironment):
        self.env = env

    async def list_tasks(self, project: str | None = None) -> list[dict]:
        """List tasks in kata."""
        cmd = ["kata", "list", "--json"]
        if project:
            cmd.extend(["--project", project])

        rc, stdout, stderr = await self.env.exec("kata-daemon", cmd)
        if rc != 0:
            raise RuntimeError(f"kata list failed: {stderr}")

        return json.loads(stdout) if stdout.strip() else []

    async def show_task(self, task_id: str) -> dict:
        """Show task details."""
        cmd = ["kata", "show", task_id, "--json"]
        rc, stdout, stderr = await self.env.exec("kata-daemon", cmd)
        if rc != 0:
            raise RuntimeError(f"kata show failed: {stderr}")

        return json.loads(stdout)

    async def create_task(
        self,
        title: str,
        body: str,
        project: str,
        labels: list[str] | None = None,
    ) -> str:
        """Create a task and return its ID."""
        cmd = ["kata", "new", title, "--project", project, "--body", body]
        if labels:
            for label in labels:
                cmd.extend(["--label", label])

        rc, stdout, stderr = await self.env.exec("kata-daemon", cmd)
        if rc != 0:
            raise RuntimeError(f"kata new failed: {stderr}")

        # Parse task ID from output (format: "Created task: <project>#<id>")
        task_ref = stdout.strip().split(":")[-1].strip()
        return task_ref


@pytest.fixture
def scenario_loader():
    """Load test scenarios from JSON files."""
    scenarios_dir = Path(__file__).parent / "fixtures" / "scenarios"

    def load(filename: str) -> dict:
        with open(scenarios_dir / filename) as f:
            return json.load(f)

    return load


@pytest.fixture
def fixture_loader():
    """Load test fixtures (comments, issues, etc.)."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    def load(filename: str) -> dict | list:
        with open(fixtures_dir / filename) as f:
            return json.load(f)

    return load
