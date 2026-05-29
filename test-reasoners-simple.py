#!/usr/bin/env python3
"""
Simple test to verify worker reasoners don't crash.

Tests by importing the worker module directly and calling reasoners.
"""
import asyncio
import sys
import os

# Set environment variables needed for worker
os.environ.setdefault("AGENTFIELD_URL", "http://agentfield:8080")
os.environ.setdefault("KATA_SERVER", "http://127.0.0.1:7878")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


async def test_run_roborev():
    """Test the run_roborev reasoner by calling it directly."""
    print("\n" + "=" * 70)
    print("Test: run_roborev reasoner")
    print("=" * 70)

    try:
        # Import the worker module to get access to reasoners
        from nd.worker import agent

        print("\n  Calling run_roborev directly...")
        print("  (Testing with existing worktree...)")

        # Call the reasoner directly (it's decorated with @app.reasoner())
        result = await agent.run_roborev(
            repo_path="/var/nd/work/langextract-bedrock-f4yn",
            commit_sha="HEAD",
            max_iterations=1,
        )

        print(f"  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")

        passed = result.get("passed")
        print(f"  ✓ Roborev passed: {passed}")

        if not passed:
            findings = result.get("final_findings", [])
            print(f"  ✓ Findings count: {len(findings)}")
            if findings:
                print(f"  ✓ First finding: {findings[0][:100] if findings[0] else 'empty'}")

        if result.get("error"):
            print(f"  ⚠ Error reported: {result['error']}")

        return True

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cleanup_workspace():
    """Test the cleanup_workspace reasoner."""
    print("\n" + "=" * 70)
    print("Test: cleanup_workspace reasoner")
    print("=" * 70)

    try:
        from nd.worker import agent

        print("\n  Calling cleanup_workspace...")

        result = await agent.cleanup_workspace(
            repo_path="/tmp/test-workspace",
            bare_path="/tmp/test-bare",
            branch="nd/test-branch-abc123",
        )

        print(f"  ✓ Reasoner executed successfully")
        print(f"  ✓ Result: {result}")

        return True

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_prepare_workspace():
    """Test that prepare_workspace doesn't crash."""
    print("\n" + "=" * 70)
    print("Test: prepare_workspace reasoner")
    print("=" * 70)

    try:
        from nd.worker import agent

        print("\n  Calling prepare_workspace...")

        result = await agent.prepare_workspace(
            platform="github",
            platform_host="github.com",
            repo_owner="andyxhadji",
            repo_name="test-repo",
            head_branch=None,
            base_branch="main",
            task_slug="test-reasoner-xyz789",
            issue_short_id="xyz789",
        )

        print(f"  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")
        print(f"  ✓ Prepared: {result.get('prepared')}")

        if result.get("error"):
            print(f"  ⚠ Error (may be expected): {result['error'][:100]}")

        return True

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all reasoner tests."""
    print("\n" + "=" * 70)
    print("WORKER REASONER SMOKE TESTS")
    print("=" * 70)
    print("\nTesting that worker reasoners execute without crashing.")
    print("These tests import the worker module and call reasoners directly.")

    results = {}

    # Test each reasoner
    tests = [
        ("run_roborev", test_run_roborev),
        ("cleanup_workspace", test_cleanup_workspace),
        ("prepare_workspace", test_prepare_workspace),
    ]

    for test_name, test_func in tests:
        try:
            passed = await test_func()
            results[test_name] = passed
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    pass_count = sum(results.values())
    total_count = len(results)

    print(f"\nPassed: {pass_count}/{total_count}")

    if all_passed:
        print("\n🎉 All reasoner smoke tests passed!")
        print("\nWorker reasoners are functional:")
        print("  - run_roborev: Calls roborev service for code quality")
        print("  - cleanup_workspace: Removes worktrees and branches")
        print("  - prepare_workspace: Creates isolated git worktrees")
    else:
        print("\n⚠ Some reasoner tests failed. Review the output above.")

    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Tests failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
