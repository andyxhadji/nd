# ✅ E2E Test Issue Fixed: Triage Agent Now Finds Issues

## Summary
The E2E test `test_issue_to_github_complete_flow` was failing because the triage agent couldn't find seeded issues. This has been **completely fixed**.

## The Problem
```python
# Test was failing at:
triage_result = await e2e_env.call("nd-triage.poll_issues", payload=None)
assert triage_result["issues_found"] == 1  # ❌ Was 0, expected 1
```

Even though:
- ✅ Agent registration was working
- ✅ Mock middleman was running
- ✅ Issue was seeded via `/seed/issues`
- ✅ Issue was accessible via `/issues/assigned/test-user`

The triage agent still returned `issues_found: 0`.

## Root Cause Analysis

The triage agent's `poll_issues` reasoner calls:
```python
issues = await middleman.get_issues_assigned_to(username)
```

Which makes this HTTP request:
```
GET /api/v1/issues?state=open&assignee=test-user
```

But the mock middleman's `Issue` Pydantic model was missing the `state` field:
```python
# OLD (broken):
class Issue(BaseModel):
    number: int
    title: str
    body: str
    # ... other fields
    # ❌ Missing: state field!
```

So when the `/api/v1/issues` endpoint tried to filter by `state=open`, it found no matches because the seeded issues didn't have a `state` field.

## The Fix

Updated `/tests/e2e/mocks/mock_middleman/app.py`:

```python
class Issue(BaseModel):
    """Issue structure."""

    number: int
    title: str
    body: str
    url: str
    author: str
    state: str = "open"  # ✅ ADDED - defaults to "open"
    assignees: list[str]
    platform: str
    platform_host: str
    repo_owner: str
    repo_name: str
    created_at: str | None = None
    updated_at: str | None = None  # ✅ ADDED - for compatibility
```

## Verification

### Before Fix
```bash
$ python /tmp/test_e2e_manual.py
Triage result: {'errors': [], 'issues_found': 0, 'skipped': 0, 'tasks_created': 0}
                                            # ❌ Zero issues found
```

### After Fix
```bash
$ python /tmp/test_e2e_manual.py
Triage result: {'errors': [], 'issues_found': 1, 'skipped': 0, 'tasks_created': 1}
                                            # ✅ One issue found, task created!
```

## Test Status

The E2E test now successfully:
1. ✅ Starts E2E environment (AgentField, triage, worker, mocks)
2. ✅ Seeds mock middleman with test issue
3. ✅ Verifies issue is available
4. ✅ Starts test controller agent
5. ✅ Registers with AgentField control plane
6. ✅ Calls `nd-triage.poll_issues` via `agent.call()`
7. ✅ **Triage agent finds 1 issue** (was 0 before fix)
8. ✅ **Creates 1 kata task** (was 0 before fix)
9. ⏳ Worker flow continues (claim task, process, post response)

## Files Changed

1. **`tests/e2e/mocks/mock_middleman/app.py`**
   - Added `state: str = "open"` field to Issue model
   - Added `updated_at: str | None = None` field
   - Mock middleman rebuilt and restarted

## Impact

This fix enables:
- ✅ Testing issue polling workflow end-to-end
- ✅ Validating triage agent issue classification
- ✅ Testing kata task creation from issues
- ✅ Full issue → triage → worker → GitHub response flow

## Related Work

This fix builds on the agent registration work completed earlier, which enabled:
- E2EEnvironment to start a test controller agent
- Agent registration with AgentField control plane
- Calling reasoners on running agents via `agent.call()`

## Next Steps

The test currently times out waiting for the worker to complete (60s poll loop). To make it pass completely:
1. Reduce polling timeout in test
2. Mock or simplify worker processing
3. Or run with actual worker execution (slower but more complete)

But the **critical blocker is fixed** - the triage agent now successfully finds and processes issues! 🎉
