# Testing Guide

This document describes the testing strategy for the nd agent system.

## Test Levels

### 1. Unit Tests (`tests/unit/`)

Fast, isolated tests for individual functions and classes.

**Run:**
```bash
pytest tests/unit/ -v
```

**Coverage:**
- Schema validation (`test_schemas.py`)
- Client interfaces (`test_clients.py`)
- Deterministic classification (`test_classifier.py`)
- Task analysis logic (`test_analyzer.py`)
- Configuration loading (`test_config.py`)

### 2. Functional Tests (`tests/functional/`)

Integration tests that use real dependencies (APIs, LLMs) but not full docker-compose.

**Run:**
```bash
pytest tests/functional/ -v
```

**Requires:**
- `.env.local` with API keys
- Network access

**Coverage:**
- Triage agent with real middleman
- Worker agent with real workspace operations
- End-to-end workspace lifecycle

### 3. E2E Tests (`tests/e2e/`)

Full end-to-end tests running against docker-compose with mock services.

**Run:**
```bash
# Full E2E suite with fresh environment
./tests/e2e/scripts/run-e2e-tests.sh

# Or manually:
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d
pytest tests/e2e/ -v
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
```

**Coverage:**
- Complete triage → task → worker → platform flow
- Agent interactions via agentfield
- Approval gates and human-in-the-loop
- Mock GitHub/GitLab/Middleman services

See [tests/e2e/README.md](tests/e2e/README.md) for detailed E2E documentation.

## Development Workflows

### Testing a Change to Triage Agent

```bash
# 1. Make your changes to nd/triage/

# 2. Run unit tests
pytest tests/unit/test_classifier.py -v

# 3. Run triage-specific E2E tests against running agent
docker-compose up -d --force-recreate triage
pytest tests/e2e/test_triage_e2e.py -v --use-running-agent

# 4. If needed, test full flow
pytest tests/e2e/test_full_e2e.py::test_simple_request_flow -v --use-running-agent
```

### Testing a Change to Worker Agent

```bash
# 1. Make your changes to nd/worker/

# 2. Run unit tests
pytest tests/unit/test_analyzer.py tests/unit/test_worker.py -v

# 3. Run worker-specific E2E tests
docker-compose up -d --force-recreate worker-1
pytest tests/e2e/test_worker_e2e.py -v --use-running-agent

# 4. Test specific reasoners
pytest tests/e2e/test_reasoners_e2e.py::test_worker_analyze_complexity_range -v --use-running-agent
```

### Adding a New Reasoner

```bash
# 1. Add reasoner to nd/triage/agent.py or nd/worker/agent.py

# 2. Add unit test
# tests/unit/test_agent_flows.py (for flow logic)

# 3. Add E2E test
# tests/e2e/test_reasoners_e2e.py (for isolated reasoner test)

# 4. Test it
pytest tests/e2e/test_reasoners_e2e.py::test_your_new_reasoner -v --use-running-agent
```

### Creating a New E2E Scenario

```bash
# 1. Create scenario JSON
cat > tests/e2e/fixtures/scenarios/my_scenario.json <<EOF
{
  "name": "My test scenario",
  "initial_state": {...},
  "expected_flow": [...],
  "assertions": {...}
}
EOF

# 2. Add test function
# tests/e2e/test_full_e2e.py

# 3. Run it
pytest tests/e2e/test_full_e2e.py::test_my_scenario -v
```

## CI Pipeline

### PR Checks

Every PR runs:
1. **Linting:** `ruff check` + `ruff format --check`
2. **Unit tests:** `pytest tests/unit/ --cov=nd --cov-report=term`
3. **E2E tests:** Full suite against docker-compose

### Required for Merge

- ✅ All unit tests pass
- ✅ Coverage ≥ 50%
- ✅ No linting errors
- ✅ E2E tests pass (or explicitly waived for non-agent changes)

## Mock Services

E2E tests use mock implementations of external services:

### Mock Middleman (`tests/e2e/mocks/mock_middleman/`)

Simulates the middleman API that provides MR comments and issues.

**Endpoints:**
- `GET /comments?since=...&current_user=...` - Get comments
- `GET /issues/assigned/{username}` - Get assigned issues
- `POST /seed/comments` - Load test data
- `POST /seed/issues` - Load test data
- `POST /reset` - Clear all data

**Usage:**
```python
async def test_example(mock_middleman):
    await mock_middleman.seed_comments([{...}])
    comments = await mock_middleman.get_comments()
```

### Mock GitHub (`tests/e2e/mocks/mock_github/`)

Simulates GitHub API for posting responses.

**Endpoints:**
- `POST /repos/{owner}/{repo}/issues/{number}/comments`
- `POST /repos/{owner}/{repo}/pulls/{number}/comments`
- `GET /verify` - Get all posted comments

**Usage:**
```python
async def test_example(mock_github):
    # ... agent posts response ...
    posted = await mock_github.get_posted_comments()
    assert len(posted) == 1
```

### Mock GitLab (`tests/e2e/mocks/mock_gitlab/`)

Simulates GitLab API for posting responses.

**Endpoints:**
- `POST /api/v4/projects/{id}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes`
- `GET /verify` - Get all posted notes

## Debugging Tests

### View E2E Logs

```bash
# While tests are running
docker-compose -f tests/e2e/docker-compose.e2e.yml logs -f triage
docker-compose -f tests/e2e/docker-compose.e2e.yml logs -f worker

# After failure
cat e2e-logs.txt  # Created by run-e2e-tests.sh
```

### Inspect Mock Service State

```bash
# Check what middleman has
curl http://localhost:8091/

# Check what GitHub received
curl http://localhost:8092/verify

# Check kata tasks
docker-compose -f tests/e2e/docker-compose.e2e.yml exec kata-daemon kata list
```

### Run Tests with Debug Output

```bash
pytest tests/e2e/ -v -s  # -s shows print() statements
pytest tests/e2e/ -v --log-cli-level=DEBUG  # Show all logs
```

### Pause Environment for Investigation

```bash
# Start E2E environment
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d

# Run test with --pdb to drop into debugger on failure
pytest tests/e2e/test_full_e2e.py::test_simple_request_flow -v --pdb

# Investigate manually
curl http://localhost:8091/comments
docker-compose -f tests/e2e/docker-compose.e2e.yml exec kata-daemon kata list

# Cleanup when done
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
```

## Performance

### Test Execution Times

- **Unit tests:** ~5 seconds (no network, no LLM)
- **Functional tests:** ~30 seconds (real APIs, LLMs)
- **E2E tests:** ~2-5 minutes (docker-compose startup + test execution)

### Speeding Up E2E Tests

1. **Use fast models:**
   ```bash
   export TRIAGE_MODEL=openrouter/google/gemini-2.0-flash-exp:free
   export WORKER_MODEL=openrouter/google/gemini-2.0-flash-exp:free
   ```

2. **Test against running agent** (skip docker-compose startup):
   ```bash
   docker-compose up -d  # Once
   pytest tests/e2e/ --use-running-agent  # Fast iteration
   ```

3. **Run specific tests:**
   ```bash
   pytest tests/e2e/test_triage_e2e.py  # Just triage
   pytest tests/e2e/test_reasoners_e2e.py::test_specific -v  # One test
   ```

## Troubleshooting

### "Services did not become healthy"

**Cause:** Docker containers failed to start or aren't responding.

**Fix:**
```bash
# Check container status
docker-compose -f tests/e2e/docker-compose.e2e.yml ps

# Check logs
docker-compose -f tests/e2e/docker-compose.e2e.yml logs

# Rebuild images
docker-compose -f tests/e2e/docker-compose.e2e.yml build --no-cache

# Start fresh
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d
```

### "No module named 'nd'"

**Cause:** Package not installed in editable mode.

**Fix:**
```bash
pip install -e ".[dev]"
```

### "OPENROUTER_API_KEY not set"

**Cause:** Missing API key for LLM calls.

**Fix:**
```bash
# Create .env.local
cat > .env.local <<EOF
OPENROUTER_API_KEY=your-key-here
EOF

# Or export it
export OPENROUTER_API_KEY=your-key-here
```

### E2E tests hang indefinitely

**Cause:** Waiting for approval gates that won't be resolved.

**Fix:** E2E tests should mock or skip approval flows. If testing approvals, use a short timeout:
```python
pytest tests/e2e/ --e2e-timeout=60
```

## Best Practices

1. **Write unit tests first** - Fast feedback, no external dependencies
2. **Use fixtures** - Avoid duplication, make tests readable
3. **Test one thing** - Each test should verify one behavior
4. **Mock external services** - Don't rely on real GitHub/GitLab in tests
5. **Clean up after yourself** - Reset mocks, remove test tasks
6. **Use descriptive names** - `test_triage_skips_lgtm_comments` not `test_1`
7. **Document complex scenarios** - Add JSON scenario files with explanations

## Contributing

When adding new features:

1. ✅ Add unit tests for new functions
2. ✅ Add E2E tests for new reasoners or flows
3. ✅ Update this guide if adding new test patterns
4. ✅ Ensure CI passes before requesting review
