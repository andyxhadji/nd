# End-to-End Testing Framework

This directory contains true end-to-end tests for the nd agent system that run against mock services in docker-compose.

## Test Suite Overview

**Total Tests:** ~30
- **Mock LLM Tests** (17): Fast, no docker - test mock service logic
- **Framework Validation** (13): Fast, no docker - validate test infrastructure
- **Flow Tests** (2): Require docker-compose - test end-to-end workflows

**Removed in Simplification (2026-05-29):**
- Individual reasoner tests → moved to `tests/unit/test_reasoner_integration.py`
- Duplicate flow tests → consolidated into `test_full_e2e.py`
- Agent registration tests → causing CI hangs, functionality tested via example tests

## Running Tests

**Fast tests only (no docker):**
```bash
pytest tests/e2e -v -m "not skip_ci" --ignore=tests/e2e/test_full_e2e.py
```

**All tests (requires docker-compose):**
```bash
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d
pytest tests/e2e -v
```

**CI configuration:**
- Skips agent integration tests (`SKIP_AGENT_INTEGRATION=true`)
- 10 minute timeout
- Runs framework validation + mock LLM tests only

## Architecture

```
tests/e2e/
├── README.md              # This file
├── conftest.py            # Shared pytest fixtures
├── docker-compose.e2e.yml # E2E test environment
├── mocks/                 # Mock service implementations
│   ├── mock_middleman/    # Mock middleman API
│   ├── mock_github/       # Mock GitHub API
│   └── mock_gitlab/       # Mock GitLab API
├── fixtures/              # Test data and scenarios
│   ├── comments.json      # Sample MR comments
│   ├── issues.json        # Sample issues
│   └── scenarios/         # Complete test scenarios
└── test_*.py              # E2E test suites

```

## Test Levels

### 1. Full E2E Tests (`test_full_e2e.py`)
- Test complete triage → worker → platform posting flow
- Verify approval gates work correctly
- Check error handling and retries
- **Run in CI and locally**

### 2. Agent-Specific Tests
- `test_triage_e2e.py` - Triage agent in isolation with mock middleman
- `test_worker_e2e.py` - Worker agent in isolation with mock kata/GitHub
- **Run locally for rapid development**

### 3. Reasoner-Level Tests
- `test_reasoners_e2e.py` - Individual reasoner functions with real dependencies
- **Run locally for debugging specific agent steps**

## Running Tests

### Full E2E Suite (CI and Local)

```bash
# Start E2E environment
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d

# Run all E2E tests
pytest tests/e2e/ -v

# Cleanup
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
```

### Test a Running Agent (Development Workflow)

```bash
# 1. Start main docker-compose with your changes
docker-compose up -d worker-1

# 2. Run agent-specific tests against the running service
pytest tests/e2e/test_worker_e2e.py -v --use-running-agent

# 3. Make changes, recreate agent
docker-compose up -d --force-recreate worker-1

# 4. Re-run tests immediately
pytest tests/e2e/test_worker_e2e.py -v --use-running-agent
```

### Quick Individual Test

```bash
# Test single reasoner
pytest tests/e2e/test_reasoners_e2e.py::test_analyze_task -v

# Test specific scenario
pytest tests/e2e/test_full_e2e.py::test_simple_request_flow -v
```

## Mock Services

### Mock Middleman
- **Purpose**: Provides MR comments and issues for triage agent
- **Port**: 8091
- **Endpoints**:
  - `GET /comments?since={timestamp}&current_user={user}`
  - `GET /issues/assigned/{username}`
  - `POST /seed` - Load test fixtures

### Mock GitHub
- **Purpose**: Receives responses from worker agent
- **Port**: 8092
- **Endpoints**:
  - `POST /repos/{owner}/{repo}/issues/{number}/comments`
  - `POST /repos/{owner}/{repo}/pulls/{number}/comments`
  - `GET /repos/{owner}/{repo}/pulls/{number}`
  - `GET /verify` - Check posted responses

### Mock GitLab
- **Purpose**: GitLab alternative to mock GitHub
- **Port**: 8093
- **Endpoints**:
  - `POST /api/v4/projects/{id}/merge_requests/{mr_iid}/discussions/{discussion_id}/notes`
  - `GET /api/v4/projects/{id}/merge_requests/{mr_iid}`
  - `GET /verify` - Check posted responses

## Test Scenarios

Scenarios are JSON files in `fixtures/scenarios/` that define:
- Initial state (comments, issues, repo state)
- Expected agent actions
- Expected final state

Example scenario structure:

```json
{
  "name": "Simple request flow",
  "description": "User requests adding a log statement",
  "initial_state": {
    "comments": [...],
    "repo_files": {...}
  },
  "expected_flow": [
    {"agent": "triage", "action": "classify", "result": "actionable"},
    {"agent": "triage", "action": "create_task", "result": "success"},
    {"agent": "worker", "action": "claim_task", "result": "claimed"},
    {"agent": "worker", "action": "execute", "result": "success"}
  ],
  "assertions": {
    "task_created": true,
    "files_changed": ["src/main.py"],
    "response_posted": true
  }
}
```

## Pytest Fixtures

### `e2e_env`
Starts docker-compose environment, waits for services to be healthy, yields control, then tears down.

### `mock_middleman`, `mock_github`, `mock_gitlab`
HTTP clients for interacting with mock services.

### `kata_client`
Client for the kata daemon running in docker-compose.

### `triage_agent`, `worker_agent`
Agent instances that can trigger reasoners in the running containers.

### `use_running_agent`
Pytest flag (`--use-running-agent`) to test against main docker-compose instead of E2E compose.

## Writing New Tests

### 1. Add a new scenario

```python
# tests/e2e/fixtures/scenarios/my_scenario.json
{
  "name": "Complex refactor",
  "initial_state": {
    "comments": [{
      "body": "Can you refactor this to use async?",
      "author": "reviewer",
      "mr_number": 42
    }]
  },
  "expected_flow": [...],
  "assertions": {...}
}
```

### 2. Write the test

```python
# tests/e2e/test_full_e2e.py
@pytest.mark.e2e
async def test_complex_refactor(e2e_env, mock_middleman, scenario_loader):
    scenario = scenario_loader("my_scenario.json")

    # Seed mock data
    await mock_middleman.seed(scenario["initial_state"]["comments"])

    # Trigger triage
    result = await e2e_env.call("nd-triage.poll_comments")
    assert result["tasks_created"] == 1

    # Trigger worker
    result = await e2e_env.call("nd-worker.claim_task")
    assert result["claimed"] is True

    # Verify assertions
    assert_scenario(scenario, e2e_env)
```

### 3. Add agent-specific tests for rapid iteration

```python
# tests/e2e/test_worker_e2e.py
@pytest.mark.e2e
async def test_analyze_complex_task(worker_agent, kata_client):
    """Test worker analysis step in isolation."""
    # Create task directly in kata
    task_id = await kata_client.create(...)

    # Call analyze_task reasoner
    result = await worker_agent.call("nd-worker.analyze_task", ...)

    # Assert
    assert result["complexity"] >= 4
    assert result["confidence"] < 70
```

## CI Integration

The E2E tests run in CI via `.github/workflows/e2e.yml`:

```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start E2E environment
        run: docker-compose -f tests/e2e/docker-compose.e2e.yml up -d
      - name: Wait for services
        run: ./tests/e2e/scripts/wait-for-services.sh
      - name: Run E2E tests
        run: pytest tests/e2e/ -v --tb=short
      - name: Collect logs on failure
        if: failure()
        run: docker-compose -f tests/e2e/docker-compose.e2e.yml logs > e2e-logs.txt
      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-logs
          path: e2e-logs.txt
```

## Debugging

### View mock service state

```bash
# Check what comments middleman has
curl http://localhost:8091/comments

# Check what GitHub received
curl http://localhost:8092/verify

# View agent logs
docker-compose -f tests/e2e/docker-compose.e2e.yml logs triage
docker-compose -f tests/e2e/docker-compose.e2e.yml logs worker
```

### Inspect kata tasks

```bash
docker-compose -f tests/e2e/docker-compose.e2e.yml exec kata-daemon kata list
docker-compose -f tests/e2e/docker-compose.e2e.yml exec kata-daemon kata show <task-id>
```

### Run tests with verbose output

```bash
pytest tests/e2e/ -v -s  # -s shows print statements
```

## Extending the Framework

### Add a new mock service

1. Create `tests/e2e/mocks/mock_myservice/`
2. Add Dockerfile and app.py
3. Add service to `docker-compose.e2e.yml`
4. Create client fixture in `conftest.py`
5. Write tests using the fixture

### Add a new agent reasoner test

1. Add test function to `test_reasoners_e2e.py`
2. Use `worker_agent.call()` or `triage_agent.call()` directly
3. Mock dependencies or use real ones based on test needs

### Add a new full E2E scenario

1. Create JSON scenario in `fixtures/scenarios/`
2. Add test function in `test_full_e2e.py`
3. Use `scenario_loader` fixture to load and execute
