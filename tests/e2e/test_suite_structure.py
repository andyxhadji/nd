"""Validate E2E test suite structure and size."""

import subprocess


def test_total_e2e_test_count():
    """Ensure E2E test count stays reasonable (< 40 tests)."""
    result = subprocess.run(
        ["pytest", "tests/e2e", "--collect-only", "-q"],
        capture_output=True,
        text=True,
    )

    # Parse "X tests collected" from output
    for line in result.stdout.split("\n"):
        if "test" in line and "collected" in line:
            count = int(line.split()[0])
            assert count <= 40, (
                f"E2E suite has grown to {count} tests. "
                "Review for duplicates or move to unit tests."
            )
            break


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

    # Should see SKIPPED marker for agent integration tests
    assert "test_simple_request_flow" in result.stdout
    assert "SKIPPED" in result.stdout
    assert "Agent integration" in result.stdout or "docker-compose" in result.stdout
