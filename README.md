# nd

Autonomous AgentField agents for processing MR comments.

## Overview

nd provides two agents that work together to automate code review comment handling:

1. **Triage Agent** - Polls middleman for new MR comments, classifies them as actionable or not, and creates kata tasks for items requiring attention.

2. **Worker Agent** - Claims tasks from kata, analyzes complexity, executes code changes via harness, runs roborev for quality validation, and posts responses after human approval.

## Quick Start

```bash
# Install
pip install -e .

# Run triage agent
python -m nd.triage

# Run worker agent
python -m nd.worker
```

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTFIELD_URL` | `http://localhost:8080` | AgentField control plane URL |
| `MIDDLEMAN_URL` | `http://localhost:8091` | Middleman API URL |
| `MIDDLEMAN_DB` | `~/.middleman/middleman.db` | Middleman SQLite database path |
| `KATA_SERVER` | (empty) | Kata daemon URL. Empty → local auto-start (host runs only). For Docker, compose sets `http://127.0.0.1:7878` so agents reach the in-compose `kata-daemon` service over the shared network namespace. |
| `AGENT_PORT` | `0` (auto) | Fixed port for the agent's HTTP server. Used by Docker Compose to give each agent (triage, worker-1, worker-2) a distinct port inside the shared `kata-daemon` netns. Empty/0 → auto-pick. |
| `CONFIDENCE_THRESHOLD` | `70` | Minimum confidence for auto-execution |
| `ROBOREV_MAX_ITERATIONS` | `3` | Max roborev-refine iterations |
| `TRIAGE_MODEL` | `openrouter/anthropic/claude-sonnet-4` | LLM model for triage |
| `WORKER_MODEL` | `openrouter/anthropic/claude-sonnet-4` | LLM model for worker |
| `AGENT_INSTANCE_ID` | `worker-1` | Unique ID for worker instance |
| `GITHUB_TOKEN` | (empty) | GitHub API token for posting responses |
| `GITLAB_TOKEN` | (empty) | GitLab API token for posting responses |
| `ND_CURRENT_USER` | (empty) | Username to filter MRs |
| `ND_ASSIGNED_USERNAMES` | (empty) | Comma-separated usernames for `poll_issues`. If empty, `poll_issues` returns an error |
| `WORKSPACE_ROOT` | `/var/nd` | Root directory for the worker's bare git cache (`<root>/repos/...`) and per-task worktrees (`<root>/work/...`). Ephemeral by default; mount as a docker volume to persist the cache across container restarts. |
| `WORKSPACE_KEEP_ON_FAILURE` | `true` | When a task fails or pauses, leave the worktree on disk for human inspection. Set to `0` / `false` to also clean up failed runs. |
| `OPENROUTER_API_KEY` | (required) | OpenRouter API key (or AWS creds for Bedrock models) |

### Setting environment variables

A starter template lives at `.env.example`. Copy it to `.env.local` (gitignored) and fill in real values before running anything that depends on it (including `docker compose up`, which mounts `.env.local` via `env_file:` and will fail if the file is missing):

```bash
cp .env.example .env.local
```

**For local runs** (`python -m nd.triage`, `pytest`, `./test-local.sh`):

Source `.env.local` before running, or use `./test-local.sh` which loads it automatically:

```bash
# .env.local
OPENROUTER_API_KEY=sk-or-...
ND_CURRENT_USER=your-username
ND_ASSIGNED_USERNAMES=alice,bob
KATA_SERVER=https://kata.example.com
GITHUB_TOKEN=ghp_...
```

**For Docker Compose** (`docker compose up`):

Both the `triage` and `worker-*` services load `.env.local` via `env_file:`. Add any required vars there:

```bash
# .env.local
ND_CURRENT_USER=your-username
ND_ASSIGNED_USERNAMES=alice,bob
KATA_SERVER=https://kata.example.com
# AWS creds if using Bedrock models
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
```

After editing `.env.local`, recreate the container so it picks up the new values:

```bash
docker compose up -d --force-recreate triage
docker compose up -d --force-recreate worker-1 worker-2
```

Verify a var made it into the container:

```bash
docker compose exec triage printenv ND_ASSIGNED_USERNAMES
```

> **Precedence note:** Variables listed under `environment:` in `docker-compose.yml` take precedence over `env_file`. If a var is interpolated like `- FOO=${FOO}` and your shell doesn't export `FOO`, it resolves to an empty string and overrides `.env.local`. To avoid surprises, define the var only in `.env.local` (not also in `environment:`), or `export` it in the shell before running compose.

### Worker workspaces

The worker prepares a fresh git worktree for every claimed task, backed by
a shared bare cache. The on-disk layout under `WORKSPACE_ROOT` (default
`/var/nd`) is:

```
/var/nd/
├── repos/<host>/<owner>/<repo>.git/   # bare cache, fetched once per task
└── work/<task-slug>/                  # per-task worktree
```

Behavior:

- **MR tasks** check out the MR's `head_branch` directly.
- **Issue tasks** create `nd/issue-<short_id>` off the repo's default
  branch (resolved from `origin/HEAD`).
- On successful completion the worker removes the worktree; on failure or
  pause it is left in place for inspection (toggle with
  `WORKSPACE_KEEP_ON_FAILURE`).

By default `/var/nd` is ephemeral — each container restart loses both the
bare cache and any leftover worktrees. To persist the cache, mount a
docker volume at `/var/nd` (or whatever you set `WORKSPACE_ROOT` to).

### Kata daemon for Docker

Compose runs kata's daemon as its own service (`kata-daemon`) listening on `127.0.0.1:7878`. The agent services (`triage`, `worker-1`, `worker-2`) all use `network_mode: "service:kata-daemon"` so they share that container's network namespace and can reach the daemon on loopback — required because kata refuses to start on a non-loopback TCP listener (see `internal/daemon/auth.go` `checkAuthStartup`).

Key consequences:

- **Tasks created from compose live in the `kata-data` named volume**, not in your host's `~/.kata/kata.db`. They are not visible to the host `kata` CLI. This is the price of running kata fully inside docker on macOS, where Docker Desktop cannot bridge host unix sockets into containers.
- **Agents share one network namespace.** Each agent binds a distinct `AGENT_PORT` (8001, 8002, 8003) to avoid collisions, and is reachable from agentfield as `kata-daemon:<AGENT_PORT>`.
- **No `KATA_HOME`/`KATA_DB`/`KATA_DB_HASH` plumbing is needed in `.env.local`** — those concepts only matter to the daemon itself, which is configured by the `kata-daemon` service block.

To inspect tasks created from compose:

```bash
docker compose exec kata-daemon kata list
docker compose exec kata-daemon kata projects list
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Middleman    │────▶│  Triage Agent   │────▶│      Kata       │
│   (MR Comments) │     │  (Classifies)   │     │    (Tasks)      │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub/GitLab  │◀────│  Worker Agent   │◀────│  Worker Agent   │
│   (Responses)   │     │ (Executes code) │     │ (Claims tasks)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │    Roborev      │
                        │ (Code review)   │
                        └─────────────────┘
```

### Human Approval Gates

The worker agent pauses for human approval at three points:

1. **Spec Review** - For low-confidence tasks, a spec is generated and requires approval
2. **Roborev Failure** - If roborev finds issues that can't be auto-fixed
3. **Response Approval** - All responses require approval before posting

## Docker Deployment

```bash
# Development with all services
docker compose up

# Test environment
docker compose -f docker-compose.test.yml up

# Run tests in container
docker compose -f docker-compose.test.yml run test-runner
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run functional tests
pytest tests/functional/ -v

# Run with coverage
pytest --cov=nd
```

## Project Structure

```
nd/
├── __init__.py                 # Package init, version
├── schemas.py                  # All Pydantic models (shared)
├── config.py                   # Environment config loader
├── clients/
│   ├── __init__.py
│   ├── middleman.py            # Middleman API client
│   ├── kata.py                 # Kata CLI wrapper
│   ├── platform.py             # GitHub/GitLab API posting
│   └── workspace.py            # Bare git cache + per-task worktrees
├── triage/
│   ├── __init__.py
│   ├── agent.py                # Triage agent definition
│   ├── classifier.py           # Actionable classification logic
│   └── __main__.py             # Entry point: python -m nd.triage
├── worker/
│   ├── __init__.py
│   ├── agent.py                # Worker agent definition
│   ├── analyzer.py             # Task complexity analysis
│   └── __main__.py             # Entry point: python -m nd.worker
tests/
├── unit/                       # Unit tests
├── functional/                 # Functional tests
```

## License

MIT
