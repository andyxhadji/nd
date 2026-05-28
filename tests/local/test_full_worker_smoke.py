"""Local-only full worker smoke test.

This intentionally is not a CI test. It runs docker compose, creates a real
kata task, lets worker-1 claim it, and waits for a real GitHub pull request.
Set ND_RUN_FULL_WORKER_SMOKE=1 to run it.
"""

import json
import os
import shlex
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from nd.clients.kata import KataClient

pytestmark = [pytest.mark.local]

RUN_ENV = "ND_RUN_FULL_WORKER_SMOKE"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_env() -> dict[str, str]:
    env = os.environ.copy()
    env_file = _repo_root() / ".env.local"
    if env_file.exists():
        for raw_line in env_file.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), shlex.split(value.strip())[0] if value.strip() else "")
    return env


def _run(
    args: list[str],
    *,
    env: dict[str, str],
    input_text: str | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=_repo_root(),
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(args)}\n"
            f"exit: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _ensure_aws_credentials(env: dict[str, str]) -> None:
    if env.get("AWS_ACCESS_KEY_ID") and env.get("AWS_SECRET_ACCESS_KEY"):
        return

    profile = env.get("ND_SMOKE_AWS_PROFILE", "mba-horizon")
    result = _run(
        ["aws", "configure", "export-credentials", "--profile", profile, "--format", "env"],
        env=env,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"missing AWS credentials and could not export profile {profile!r}; "
            "run saml2aws login or export AWS_* first"
        ) from None

    for raw_line in result.stdout.splitlines():
        if not raw_line.startswith("export ") or "=" not in raw_line:
            continue
        key, value = raw_line[len("export ") :].split("=", 1)
        env[key] = shlex.split(value)[0] if value else ""


def _compose(
    args: list[str],
    *,
    env: dict[str, str],
    input_text: str | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run(
        ["docker", "compose", *args],
        env=env,
        input_text=input_text,
        timeout=timeout,
        check=check,
    )


def _github_json(path: str, *, env: dict[str, str]) -> object:
    token = env.get("GITHUB_TOKEN")
    if not token:
        raise AssertionError("GITHUB_TOKEN is required for the full worker smoke")

    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def _ready_nd_tasks(env: dict[str, str]) -> list[dict]:
    result = _compose(
        [
            "exec",
            "-T",
            "kata-daemon",
            "sh",
            "-lc",
            (
                "for p in test sweets langextract-bedrock test-variable; do "
                'kata ready --project "$p" --label nd --unowned --json || true; '
                "done"
            ),
        ],
        env=env,
    )
    tasks = []
    for line in result.stdout.splitlines():
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        tasks.extend(payload.get("issues") or [])
    return tasks


def test_full_worker_creates_real_pull_request() -> None:
    if os.environ.get(RUN_ENV) != "1":
        pytest.skip(f"set {RUN_ENV}=1 to run the local full worker smoke")

    env = _load_env()
    _ensure_aws_credentials(env)

    owner = env.get("ND_SMOKE_REPO_OWNER", "fh-ahadjigeorgiou")
    repo = env.get("ND_SMOKE_REPO_NAME", "test-variable")
    project = env.get("ND_SMOKE_PROJECT", repo)
    timeout_seconds = int(env.get("ND_FULL_WORKER_SMOKE_TIMEOUT", "900"))

    _compose(["up", "-d", "--force-recreate", "worker-1", "worker-2"], env=env, timeout=180)

    sdk_probe = _compose(
        [
            "exec",
            "-T",
            "worker-1",
            "sh",
            "-lc",
            (
                "python - <<'PY'\n"
                "import asyncio\n"
                "from claude_agent_sdk import ClaudeAgentOptions, query\n"
                "async def main():\n"
                "    opts = ClaudeAgentOptions(cwd='/tmp', allowed_tools=['Read'], "
                "permission_mode='acceptEdits', max_turns=1)\n"
                "    async for msg in query(prompt='Reply with exactly: ok', options=opts):\n"
                "        print(type(msg).__name__, getattr(msg, 'result', ''))\n"
                "asyncio.run(main())\n"
                "PY"
            ),
        ],
        env=env,
        timeout=120,
    )
    assert "ok" in sdk_probe.stdout
    assert "Not logged in" not in sdk_probe.stdout

    existing_ready = _ready_nd_tasks(env)
    assert existing_ready == [], (
        "full worker smoke requires an empty unowned nd queue so claim_task "
        f"does not pick unrelated work: {existing_ready!r}"
    )

    smoke_id = f"smoke-{int(time.time())}"
    body = KataClient.build_issue_task_body(
        issue_url=f"https://github.com/{owner}/{repo}/issues/1001",
        issue_title="ND full worker smoke",
        issue_number=1001,
        platform="github",
        platform_host="github.com",
        repo_owner=owner,
        repo_name=repo,
        issue_author="codex-smoke",
        issue_body=(
            "Smoke test: make a tiny harmless documentation change in this repository. "
            "Add one short line to CHANGELOG.md mentioning the ND worker smoke. "
            "Leave the edit in the repository for the worker to commit."
        ),
        assignees=[owner],
    )
    created = _compose(
        [
            "exec",
            "-T",
            "kata-daemon",
            "kata",
            "create",
            f"ND full worker smoke {smoke_id}",
            "--force-new",
            "--body-stdin",
            "--project",
            project,
            "--label",
            "nd",
            "--label",
            "from-issue",
            "--idempotency-key",
            f"nd-full-worker-{smoke_id}",
            "--json",
        ],
        env=env,
        input_text=body,
    )
    issue = json.loads(created.stdout)["issue"]
    short_id = issue["short_id"]
    branch = f"nd/issue-{short_id}"

    trigger = _compose(
        [
            "exec",
            "-T",
            "kata-daemon",
            "sh",
            "-lc",
            (
                "curl --max-time 20 -sS -X POST "
                "http://127.0.0.1:8002/reasoners/claim_task "
                "-H 'Content-Type: application/json' -d '{}'"
            ),
        ],
        env=env,
        timeout=30,
        check=False,
    )
    assert trigger.returncode in (0, 28)

    head = urllib.parse.quote(f"{owner}:{branch}", safe="")
    deadline = time.monotonic() + timeout_seconds
    pulls: list[dict] = []
    while time.monotonic() < deadline:
        pulls = _github_json(
            f"/repos/{owner}/{repo}/pulls?state=open&head={head}",
            env=env,
        )
        if pulls:
            break
        time.sleep(10)

    assert pulls, f"timed out waiting for pull request from {branch}"
    pull = pulls[0]
    files = _github_json(f"/repos/{owner}/{repo}/pulls/{pull['number']}/files", env=env)

    assert pull["html_url"].startswith(f"https://github.com/{owner}/{repo}/pull/")
    assert pull["head"]["ref"] == branch
    assert {file["filename"] for file in files} == {"CHANGELOG.md"}

    # Verify the worker execution didn't fail (but may be paused for approval)
    worker_logs = _compose(
        ["logs", "worker-1", "--tail=500"],
        env=env,
        check=False,
    )
    # Check for execution failures
    if "reasoner.failed" in worker_logs.stdout:
        # Look for failures related to this specific task
        failed_lines = [
            line for line in worker_logs.stdout.splitlines()
            if "reasoner.failed" in line
        ]
        if failed_lines:
            raise AssertionError(
                f"Worker execution failed for task {short_id}. "
                f"Last failure: {failed_lines[-1][:300]}"
            )

    # The worker always pauses for response approval after creating the PR.
    # Verify the task is either closed (if auto-approved somehow) or paused for approval.
    task_status = _compose(
        [
            "exec",
            "-T",
            "kata-daemon",
            "kata",
            "show",
            "--project",
            project,
            "--json",
            short_id,
        ],
        env=env,
    )
    task_data = json.loads(task_status.stdout)
    status = task_data["issue"]["status"]

    # Success: PR created, task is paused for response approval
    # (The human approval gate is part of the design - not a failure)
    assert status in ("open", "closed"), (
        f"task {short_id} should be open (paused for approval) or closed, "
        f"got status={status}"
    )
