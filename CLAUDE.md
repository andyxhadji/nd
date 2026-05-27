# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project: nd

Autonomous AgentField agents that process MR comments and assigned issues. Two agents work together:

- **Triage agent** (`nd/triage/`) — polls middleman for new MR comments and assigned issues, classifies them, and creates kata tasks for actionable items.
- **Worker agent** (`nd/worker/`) — claims tasks from kata, analyzes complexity, executes code via the harness, validates with roborev, and posts responses after human approval.

Both agents are built on the `agentfield` framework using `@app.reasoner()`-decorated async functions. Reasoners tagged `entry` are the polling/claiming entrypoints (their cron decorators are currently disabled — they are triggered manually).

## Layout

```
nd/
├── schemas.py           # All Pydantic models — shared between triage & worker
├── config.py            # Single Config dataclass loaded from env
├── clients/
│   ├── middleman.py     # MR comments + assigned issues
│   ├── kata.py          # Task creation, claim, label, comment, close
│   └── platform.py      # GitHub/GitLab posting
├── triage/agent.py      # Reasoners: poll_comments, classify_actionable,
│                        #            create_task, poll_issues, create_issue_task
└── worker/agent.py      # Reasoners: claim_task, process_task, analyze_task,
                         #            plan_changes, execute_changes, run_roborev,
                         #            draft_response, post_response, finalize_task
tests/
├── unit/                # Fast, isolated — required to pass in CI
└── functional/          # Integration tests, need API keys
docs/superpowers/
├── specs/               # Design docs (issue polling, agentfield design)
└── plans/               # Implementation plans
```

## Conventions

- **Python 3.11+**, async-first (`asyncio`, `httpx`).
- **All schemas live in `nd/schemas.py`** — do not create per-module schema files.
- **Config is a frozen dataclass** loaded once from env (`config.py`). Add new settings there with a default; never read `os.getenv` from agent code.
- **Reasoners return `dict`**, built by `Pydantic.model_dump()` from a schema in `nd/schemas.py`. Inputs to reasoners are individual kwargs (not a single model) so they serialize cleanly through `app.call`.
- **Determinism first, LLM fallback** — `triage/classifier.py` and `worker/analyzer.py` try a deterministic pass before calling `app.ai(...)`. Preserve that pattern when extending.
- **Idempotency** — task creation uses `comment_dedupe_key` (for comments) or `issue:{url}` (for issues) as the kata `idempotency_key`, plus a pre-create `kata.search` duplicate check.
- **Human approval gates** are explicit `await app.pause(...)` calls with 72-hour expiry in three places: low-confidence spec review, roborev failure, response posting.

## Workflows

```bash
# Install (editable + dev tools)
pip install -e ".[dev]"

# Run unit tests (CI-equivalent)
pytest tests/unit -v

# Run all tests
pytest

# Lint / format (must pass in CI)
ruff check .
ruff format --check .

# Local helper (loads .env.local, sets AWS creds from mba-horizon profile)
./test-local.sh test          # unit tests
./test-local.sh functional    # functional tests (needs API keys)
./test-local.sh classify "comment text"
./test-local.sh analyze "task text"
./test-local.sh docker        # docker compose up + tail logs
```

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, unit tests, and enforces ≥50% coverage. Match this locally before pushing.

## Running the agents

```bash
python -m nd.triage    # entry: nd/triage/__main__.py
python -m nd.worker    # entry: nd/worker/__main__.py
```

Cron schedules on `poll_comments` and `claim_task` are intentionally commented out — invoke entrypoints manually (or via the agentfield control plane) for now.

## Configuration (env vars)

Required: `OPENROUTER_API_KEY` (or Bedrock creds for the bedrock models).

Common knobs:
- `CONFIDENCE_THRESHOLD` (default 70) — below this, worker pauses for spec review.
- `ROBOREV_MAX_ITERATIONS` (default 3).
- `ND_CURRENT_USER` — filters MRs in middleman polling.
- `ND_ASSIGNED_USERNAMES` — comma-separated list for `poll_issues`. If empty, `poll_issues` returns an error result.
- `TRIAGE_MODEL` / `WORKER_MODEL` — falls back to `ANTHROPIC_DEFAULT_SONNET_MODEL`.

Full table is in `README.md`.

## When adding a feature

1. Check `docs/superpowers/specs/` and `docs/superpowers/plans/` — features here are typically spec'd before implementation. Follow the existing spec/plan style for non-trivial work.
2. Add or update a schema in `nd/schemas.py` first.
3. Add a deterministic helper in `triage/classifier.py` or `worker/analyzer.py` if applicable.
4. Add the reasoner to `triage/agent.py` or `worker/agent.py`. Tag with `entry` only if it's a polling/claiming entrypoint.
5. Unit-test the helper and the reasoner wiring under `tests/unit/`.
6. Run `ruff check . && ruff format --check . && pytest tests/unit` before committing.

## Things to avoid

- Don't bypass the dedupe / idempotency checks in `create_task` or `create_issue_task`.
- Don't remove the human approval `app.pause` calls in `process_task` — those gates are part of the design.
- Don't read env vars outside `nd/config.py`.
- Don't introduce per-module Pydantic models — keep them in `nd/schemas.py`.
- Don't re-enable the cron decorators on entry reasoners without coordinating — the project is currently manual-trigger only.
