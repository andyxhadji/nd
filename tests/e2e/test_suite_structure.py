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
    """Ensure agent integration tests are properly deselected when using skip_ci marker."""
    # Run pytest with -m "not skip_ci" to see what tests are selected
    result = subprocess.run(
        ["pytest", "tests/e2e/test_full_e2e.py", "-v", "--tb=no", "-m", "not skip_ci"],
        capture_output=True,
        text=True,
    )
    # Exit code 5 means no tests were selected (both were deselected), which is what we want
    # Exit code 0 would mean tests ran and passed
    assert result.returncode in (0, 5), f"Unexpected pytest exit code: {result.returncode}"

    # Should see "2 deselected" in output for the two skip_ci tests
    output = result.stdout
    assert "2 deselected" in output, (
        "Expected 2 tests with @pytest.mark.skip_ci to be deselected "
        "when running with -m 'not skip_ci'"
    )
