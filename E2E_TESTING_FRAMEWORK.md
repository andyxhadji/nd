# E2E Testing Framework - Implementation Summary

This document summarizes the end-to-end testing framework created for the nd agent system.

## What Was Built

A comprehensive E2E testing framework that provides:

1. **True end-to-end tests** - Full agent workflows with mock services
2. **Agent-specific tests** - Test individual agents in isolation
3. **Fast iteration mode** - Test against running agents without restarting
4. **Extensible architecture** - Easy to add new scenarios and agents
5. **CI integration** - Automated testing in GitHub Actions

## Directory Structure

```
tests/e2e/
├── README.md                     # Comprehensive documentation
├── QUICKSTART.md                 # 5-minute getting started guide
├── pytest.ini                    # Pytest configuration
├── conftest.py                   # Shared fixtures and utilities
├── example_test.py               # Example tests showing patterns
│
├── docker-compose.e2e.yml        # E2E environment definition
│
├── test_full_e2e.py              # Full workflow tests
├── test_triage_e2e.py            # Triage agent isolation tests
├── test_worker_e2e.py            # Worker agent isolation tests
├── test_reasoners_e2e.py         # Individual reasoner tests
│
├── fixtures/                     # Test data
│   ├── comments.json             # Sample MR comments
│   ├── issues.json               # Sample issues
│   └── scenarios/                # Complex test scenarios
│       ├── simple_request.json
│       ├── complex_refactor.json
│       └── issue_flow.json
│
├── mocks/                        # Mock service implementations
│   ├── mock_middleman/
│   │   ├── Dockerfile
│   │   └── app.py
│   ├── mock_github/
│   │   ├── Dockerfile
│   │   └── app.py
│   └── mock_gitlab/
│       ├── Dockerfile
│       └── app.py
│
└── scripts/                      # Helper scripts
    ├── run-e2e-tests.sh          # Run full E2E suite
    ├── test-running-agent.sh     # Test against running agents
    └── wait-for-services.sh      # Wait for service health
```

## Key Features

### 1. Multiple Test Levels

**Full E2E Tests** (`test_full_e2e.py`)
- Complete triage → worker → platform flow
- Tests entire system integration
- Runs in CI and locally

**Agent-Specific Tests** (`test_triage_e2e.py`, `test_worker_e2e.py`)
- Test individual agents in isolation
- Fast feedback during development
- Can test against running agents

**Reasoner Tests** (`test_reasoners_e2e.py`)
- Test individual reasoner functions
- Debug specific agent steps
- Quick iteration on logic changes

### 2. Mock Services

**Mock Middleman** - Simulates MR comment and issue source
- Seed test data via POST /seed/comments and /seed/issues
- Query via GET /comments and GET /issues/assigned/{user}
- Reset state via POST /reset

**Mock GitHub** - Captures posted responses
- Accepts PR/issue comments
- Verify posted content via GET /verify
- Reset state via POST /reset

**Mock GitLab** - Alternative to GitHub
- Accepts MR discussion notes
- Verify posted content via GET /verify
- Reset state via POST /reset

### 3. Test Fixtures

**Pytest Fixtures**
- `e2e_env` - Docker-compose environment controller
- `mock_middleman`, `mock_github`, `mock_gitlab` - HTTP clients
- `kata_client` - Kata daemon client
- `scenario_loader` - Load test scenarios from JSON
- `fixture_loader` - Load test data from JSON
- `use_running_agent` - Flag to test against main docker-compose

**JSON Fixtures**
- `comments.json` - Sample MR comments (actionable and non-actionable)
- `issues.json` - Sample GitHub/GitLab issues
- `scenarios/*.json` - Complete test scenarios with expected flows

### 4. Development Workflows

**Test a Specific Agent**
```bash
# Make changes to worker
docker-compose up -d --force-recreate worker-1

# Test it immediately
pytest tests/e2e/test_worker_e2e.py -v --use-running-agent
```

**Add a New Test**
```bash
# Add test function to test_*.py
# Run it
pytest tests/e2e/test_full_e2e.py::test_my_new_test -v
```

**Debug a Failing Test**
```bash
# Start environment with logs
docker-compose -f tests/e2e/docker-compose.e2e.yml up

# In another terminal, run test with debugger
pytest tests/e2e/test_*.py::test_failing -v --pdb
```

### 5. CI Integration

GitHub Actions workflow (`.github/workflows/e2e.yml`):
- Starts E2E environment
- Waits for service health
- Runs full E2E suite
- Collects logs on failure
- Cleans up environment

Runs on:
- Every push to main
- Every pull request
- Manual workflow dispatch

## Usage Examples

### Run Full E2E Suite

```bash
# Automated (recommended)
./tests/e2e/scripts/run-e2e-tests.sh

# Manual
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d
pytest tests/e2e/ -v
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
```

### Test Against Running Agent

```bash
# Start your development environment
docker-compose up -d

# Make changes, recreate agent
docker-compose up -d --force-recreate worker-1

# Test immediately (no startup delay!)
pytest tests/e2e/ -v --use-running-agent
```

### Run Specific Tests

```bash
# Test triage classification only
pytest tests/e2e/test_triage_e2e.py::test_classify_actionable_request -v

# Test worker analysis only
pytest tests/e2e/test_worker_e2e.py::test_analyze_simple_task -v

# Test full flow
pytest tests/e2e/test_full_e2e.py::test_simple_request_flow -v
```

### Write New Tests

See `tests/e2e/example_test.py` for patterns:

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_my_scenario(e2e_env, mock_middleman, kata_client):
    """Test description."""
    # Seed data
    await mock_middleman.seed_comments([...])

    # Trigger agent
    result = await e2e_env.call("nd-triage.poll_comments")

    # Verify
    assert result["tasks_created"] == 1
```

## Extensibility

### Adding a New Mock Service

1. Create `tests/e2e/mocks/mock_myservice/`
2. Add Dockerfile and FastAPI app
3. Add service to `docker-compose.e2e.yml`
4. Add client fixture to `conftest.py`
5. Write tests using the fixture

### Adding a New Test Scenario

1. Create JSON in `fixtures/scenarios/my_scenario.json`
2. Define initial_state, expected_flow, assertions
3. Add test function using `scenario_loader` fixture
4. Run: `pytest tests/e2e/test_full_e2e.py::test_my_scenario -v`

### Testing a New Agent

1. Add agent to `docker-compose.e2e.yml`
2. Create `tests/e2e/test_myagent_e2e.py`
3. Write tests calling `e2e_env.call("my-agent.reasoner_name")`
4. Add to CI workflow if needed

### Adding New Reasoner Tests

1. Add test to `tests/e2e/test_reasoners_e2e.py`
2. Call reasoner: `await e2e_env.call("agent.reasoner", **kwargs)`
3. Assert on return value
4. Run: `pytest tests/e2e/test_reasoners_e2e.py::test_my_reasoner -v`

## Documentation

Comprehensive documentation is provided:

- **README.md** - Full framework documentation
- **QUICKSTART.md** - 5-minute getting started guide
- **TESTING.md** - Complete testing strategy (root level)
- **example_test.py** - Annotated example tests
- **Inline comments** - All code is documented

## Benefits

1. **Confidence** - Know that agent workflows work end-to-end
2. **Speed** - Fast iteration with `--use-running-agent`
3. **Isolation** - Test agents independently
4. **Debugging** - Clear failure modes, easy to inspect state
5. **CI/CD** - Automated testing prevents regressions
6. **Extensibility** - Easy to add new scenarios and agents
7. **Documentation** - Self-documenting via test cases

## Next Steps

1. **Run the example**
   ```bash
   ./tests/e2e/scripts/run-e2e-tests.sh
   ```

2. **Read the quickstart**
   ```bash
   cat tests/e2e/QUICKSTART.md
   ```

3. **Try fast iteration**
   ```bash
   docker-compose up -d
   pytest tests/e2e/test_triage_e2e.py -v --use-running-agent
   ```

4. **Write your first test**
   - Copy example from `example_test.py`
   - Add to appropriate `test_*.py` file
   - Run and iterate

5. **Add to CI**
   - E2E workflow is already in `.github/workflows/e2e.yml`
   - Tests run automatically on PR

## Summary

This E2E testing framework provides:

✅ **Complete coverage** - Full agent workflows tested end-to-end
✅ **Fast iteration** - Test against running agents
✅ **CI integration** - Automated testing on every PR
✅ **Extensible** - Easy to add new tests and scenarios
✅ **Well documented** - Multiple guides and examples
✅ **Production-ready** - Used in actual development workflow

The framework is ready to use and will help ensure the nd agent system works reliably in production.
