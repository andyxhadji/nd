"""Validate E2E test suite structure and size."""

import subprocess


def test_total_e2e_test_count():
    """Ensure E2E test count stays reasonable (< 40 tests)."""
    result = subprocess.run(
        ["pytest", "tests/e2e", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Parse "X tests collected" from output
    found = False
    for line in result.stdout.split("\n"):
        if "test" in line and "collected" in line:
            found = True
            count = int(line.split()[0])
            assert count <= 40, (
                f"E2E suite has grown to {count} tests. "
                "Review for duplicates or move to unit tests."
            )
            break
    assert found, "Failed to parse pytest collection output — could not find 'tests collected' line"


def test_no_skipped_agent_integration_tests_in_ci():
    """Ensure agent integration tests are properly skipped when env flag is set."""
    import os

    if os.getenv("SKIP_AGENT_INTEGRATION") != "true":
        # Not running in CI mode, skip this check
        return

    # Run pytest with -v to see skip status
    result = subprocess.run(
        ["pytest", "tests/e2e/test_full_e2e.py", "-v", "--tb=no"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Should see SKIPPED marker for agent integration tests
    # Verify the test appears with SKIPPED status
    output_lines = result.stdout.split("\n")
    found_skipped = False
    for line in output_lines:
        if "test_simple_request_flow" in line and "SKIPPED" in line:
            found_skipped = True
            break
    assert found_skipped, (
        "test_simple_request_flow should be SKIPPED when SKIP_AGENT_INTEGRATION=true"
    )
