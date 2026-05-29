# E2E Testing Quick Start

Get up and running with E2E tests in 5 minutes.

## Prerequisites

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Create .env.local (E2E uses this for AWS/OpenRouter credentials)
cat > .env.local <<EOF
OPENROUTER_API_KEY=your-key-here
ND_CURRENT_USER=test-user
ND_ASSIGNED_USERNAMES=test-user,reviewer
EOF
```

## Run Full E2E Suite

```bash
# Start environment, run tests, cleanup
./tests/e2e/scripts/run-e2e-tests.sh
```

This will:
1. Start docker-compose with agents + mocks
2. Wait for services to be healthy
3. Run all E2E tests
4. Collect logs if tests fail
5. Tear down environment

## Run Specific Test

```bash
# Start environment manually
docker-compose -f tests/e2e/docker-compose.e2e.yml up -d

# Wait for health
./tests/e2e/scripts/wait-for-services.sh

# Run one test
pytest tests/e2e/test_full_e2e.py::test_simple_request_flow -v

# Cleanup
docker-compose -f tests/e2e/docker-compose.e2e.yml down -v
```

## Test Against Running Agent (Fast Iteration)

```bash
# 1. Start main docker-compose
docker-compose up -d

# 2. Make changes to nd/worker/agent.py

# 3. Recreate worker
docker-compose up -d --force-recreate worker-1

# 4. Run tests against running agent (no startup delay!)
pytest tests/e2e/test_worker_e2e.py -v --use-running-agent

# 5. Repeat steps 2-4 as needed
```

## Write Your First E2E Test

### 1. Create a test function

Edit `tests/e2e/test_full_e2e.py`:

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_my_scenario(e2e_env, mock_middleman, kata_client):
    """Test my custom scenario."""
    # Seed data
    await mock_middleman.seed_comments([{
        "body": "Fix the bug in auth.py",
        "author": "reviewer",
        "mr_number": 123,
        "mr_url": "https://github.com/org/repo/pull/123",
        "head_branch": "fix-auth",
        "base_branch": "main",
        "platform": "github",
        "platform_host": "github.com",
        "repo_owner": "org",
        "repo_name": "repo",
        "dedupe_key": "test:my-scenario:1",
        # ... other required fields
    }])

    # Trigger triage
    result = await e2e_env.call("nd-triage.poll_comments")
    assert result["tasks_created"] == 1

    # Verify task created
    tasks = await kata_client.list_tasks(project="repo")
    assert len(tasks) >= 1
```

### 2. Run it

```bash
pytest tests/e2e/test_full_e2e.py::test_my_scenario -v
```

## Common Patterns

### Test Triage Classification

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_classify_my_comment(e2e_env):
    result = await e2e_env.call(
        "nd-triage.classify_actionable",
        body="My comment text",
        author="reviewer",
        mr_title="My MR",
        mr_number=1,
    )

    assert result["actionable"] is True
    assert result["category"] == "request"
```

### Test Worker Analysis

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_analyze_my_task(e2e_env):
    result = await e2e_env.call(
        "nd-worker.analyze_task",
        comment_body="Refactor this module",
        comment_category="request",
        mr_title="Refactor",
        head_branch="refactor",
        repo_path="/tmp/test",
    )

    assert result["complexity"] >= 4
    assert result["confidence"] < 70
```

### Verify Mock Interactions

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_response_posted(e2e_env, mock_github):
    # ... workflow that posts response ...

    posted = await mock_github.get_posted_comments()
    assert len(posted) == 1
    assert "fixed" in posted[0]["body"].lower()
```

## Debugging

### View logs in real-time

```bash
# Terminal 1: Start environment
docker-compose -f tests/e2e/docker-compose.e2e.yml up

# Terminal 2: Watch agent logs
docker-compose -f tests/e2e/docker-compose.e2e.yml logs -f triage worker

# Terminal 3: Run tests
pytest tests/e2e/ -v -s
```

### Inspect state

```bash
# Check kata tasks
docker-compose -f tests/e2e/docker-compose.e2e.yml exec kata-daemon kata list

# Check mock data
curl http://localhost:8091/  # Middleman
curl http://localhost:8092/verify  # GitHub
curl http://localhost:8093/verify  # GitLab
```

### Drop into debugger

```bash
pytest tests/e2e/test_full_e2e.py::test_my_test -v --pdb
```

## Next Steps

- Read [tests/e2e/README.md](README.md) for full documentation
- Browse [tests/e2e/fixtures/scenarios/](fixtures/scenarios/) for example scenarios
- Check [TESTING.md](../../TESTING.md) for the complete testing guide
- Review existing tests in `test_*.py` files for patterns
