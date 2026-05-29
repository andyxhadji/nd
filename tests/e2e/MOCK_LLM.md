# Mock LLM for E2E Testing

This document describes the mock LLM implementation that enables E2E tests to run without API keys.

## Overview

The mock LLM service provides deterministic responses for `app.ai()` calls, eliminating the need for real LLM APIs during testing. This enables:

- **Zero API costs** - No LLM API calls during testing
- **Fast execution** - Instant responses, no network latency
- **Deterministic results** - Same input always produces same output
- **CI-friendly** - No secrets or API keys required

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     E2E Test Environment                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ Triage Agent │         │ Worker Agent │                  │
│  │              │         │              │                  │
│  │ app.ai() ────┼────┐    │ app.ai() ────┼────┐            │
│  └──────────────┘    │    └──────────────┘    │            │
│                      │                         │            │
│                      ▼                         ▼            │
│              ┌────────────────────────────────────┐         │
│              │      MockLLMService                │         │
│              │  (Pattern-based responses)         │         │
│              └────────────────────────────────────┘         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. MockLLMService (`tests/e2e/mocks/mock_llm_service.py`)

Core service providing deterministic responses:

- **`classify_comment()`** - Comment classification (actionable/non-actionable)
- **`analyze_complexity()`** - Task complexity estimation
- **`plan_changes()`** - Implementation plan generation
- **`draft_response()`** - Response text generation
- **`handle_ai_call()`** - Main dispatcher routing to appropriate mock

### 2. MockAIWrapper (`tests/e2e/mocks/mock_llm_injector.py`)

Intercepts `app.ai()` calls and routes to MockLLMService:

```python
from mock_llm_injector import patch_agentfield_ai

# Patch the agent's ai() method
patch_agentfield_ai(app)
```

### 3. Agent Wrapper Scripts

- **`triage_with_mock.py`** - Runs triage agent with mock LLM
- **`worker_with_mock.py`** - Runs worker agent with mock LLM

Both check `USE_MOCK_LLM=1` environment variable to enable mocking.

## Usage

### In Docker Compose

The E2E docker-compose environment uses mock LLM by default:

```yaml
services:
  triage:
    command: python tests/e2e/mocks/triage_with_mock.py
    environment:
      - USE_MOCK_LLM=1
    volumes:
      - ../../tests/e2e/mocks:/app/tests/e2e/mocks:ro
```

### In Tests

Mock LLM is automatically enabled when using the E2E environment:

```python
@pytest.mark.e2e
async def test_something(e2e_env):
    # app.ai() calls are automatically mocked
    result = await some_agent_function()
```

### Running Tests

```bash
# All E2E tests (with mock LLM)
pytest tests/e2e/ -v

# Just mock LLM unit tests
pytest tests/e2e/test_mock_llm.py -v

# With running docker-compose
pytest tests/e2e/ -v --use-running-agent
```

## Mock Patterns

The mock LLM uses keyword-based patterns matching the agents' deterministic fallback logic:

### Classification

```python
# Non-actionable
"LGTM" -> {actionable: False, category: "acknowledgment"}
"Thanks!" -> {actionable: False, category: "acknowledgment"}

# Actionable
"Can you...?" -> {actionable: True, category: "question"}
"Please fix..." -> {actionable: True, category: "request"}
"nit: ..." -> {actionable: True, category: "review"}
```

### Complexity

```python
"Fix typo" -> {complexity: 20, reasoning: "Simple change"}
"Add logging" -> {complexity: 30, reasoning: "Simple change"}
"Refactor authentication" -> {complexity: 85, reasoning: "Complex task"}
```

### Planning

```python
"Add tests" -> {plan: "1. Identify test cases...", estimated_files: 2}
"Fix bug" -> {plan: "1. Reproduce the issue...", estimated_files: 1}
"Refactor" -> {plan: "1. Analyze current...", estimated_files: 3}
```

## Test Results

```
✅ 17/17 mock LLM unit tests passing
✅ 36/65 total E2E tests passing
⏱️  Test execution: ~2 minutes
💰 Cost: $0 (no API calls)
```

### Passing Tests

- All mock LLM functionality tests
- Mock service integration tests
- Framework validation tests
- Infrastructure tests

### Known Limitations

**27 tests require cross-agent communication fix** - Tests that use `env.call()` to invoke agent reasoners need the E2EEnvironment's agent registration completed. This is a separate infrastructure issue from the mock LLM implementation.

The failing tests attempt to make cross-agent calls through AgentField but the test controller agent is not properly registered. Options to fix:

1. Complete the agent registration in E2EEnvironment fixture
2. Switch to direct HTTP calls to agent endpoints

See GitHub issues for tracking.

## Debugging

### Enable Mock LLM Debug Logging

```bash
export MOCK_LLM_DEBUG=1
pytest tests/e2e/test_mock_llm.py -v -s
```

This shows each mock call and response.

### Verify Mock is Active

Check docker logs:

```bash
docker compose -f tests/e2e/docker-compose.e2e.yml logs triage | grep "Mock LLM"
# Should show: "🧪 Triage agent running with Mock LLM"
```

## Adding New Mock Patterns

To add new mock patterns, edit `tests/e2e/mocks/mock_llm_service.py`:

```python
@staticmethod
def classify_comment(body: str, author: str = "") -> dict:
    body_lower = body.lower()

    # Add new pattern
    if "your new pattern" in body_lower:
        return {
            "actionable": True,
            "category": "your_category",
            "reason": "Matches your pattern",
            "confident": True
        }

    # ... existing patterns
```

Then add a test in `tests/e2e/test_mock_llm.py`:

```python
def test_classifies_your_new_pattern():
    """Test your new pattern is classified correctly."""
    result = MockLLMService.classify_comment("your new pattern")
    assert result["actionable"] is True
    assert result["category"] == "your_category"
```

## Future Enhancements

- Add more sophisticated pattern matching (regex, similarity)
- Support mock responses for other AI operations
- Add configurable mock responses via fixtures
- Record/replay mode for capturing real LLM responses

## See Also

- `tests/e2e/README.md` - E2E testing framework overview
- `tests/e2e/test_mock_llm.py` - Mock LLM test suite
- `nd/triage/classifier.py` - Real triage classification logic
- `nd/worker/analyzer.py` - Real worker analysis logic
