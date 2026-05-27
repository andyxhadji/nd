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
| `KATA_SERVER` | (empty) | Kata server URL (uses local if empty) |
| `CONFIDENCE_THRESHOLD` | `70` | Minimum confidence for auto-execution |
| `ROBOREV_MAX_ITERATIONS` | `3` | Max roborev-refine iterations |
| `TRIAGE_MODEL` | `openrouter/anthropic/claude-sonnet-4` | LLM model for triage |
| `WORKER_MODEL` | `openrouter/anthropic/claude-sonnet-4` | LLM model for worker |
| `AGENT_INSTANCE_ID` | `worker-1` | Unique ID for worker instance |
| `GITHUB_TOKEN` | (empty) | GitHub API token for posting responses |
| `GITLAB_TOKEN` | (empty) | GitLab API token for posting responses |
| `ND_CURRENT_USER` | (empty) | Username to filter MRs |
| `ND_ASSIGNED_USERNAMES` | (empty) | Comma-separated usernames for `poll_issues`. If empty, `poll_issues` returns an error |
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
│   └── platform.py             # GitHub/GitLab API posting
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
