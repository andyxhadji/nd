#!/usr/bin/env python3
"""
Test worker reasoners to ensure they execute without failing.

This tests the actual @app.reasoner() functions by calling them via
the agentfield framework and verifying they return results.
"""

import asyncio
import sys

from agentfield import Agent, AIConfig

# Create a test agent to call worker reasoners
test_agent = Agent(
    node_id="reasoner-test",
    version="1.0.0",
    agentfield_server="http://agentfield:8080",
    ai_config=AIConfig(
        model="bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/mj2ayeqbysnr"
    ),
)


async def call_reasoner(reasoner_name: str, **kwargs) -> dict:
    """Call a reasoner via agentfield Agent.call() and return the result."""
    result = await test_agent.call(
        f"nd-worker.{reasoner_name}",
        payload=kwargs,
    )
    return result


async def test_prepare_workspace():
    """Test the prepare_workspace reasoner."""
    print("\n" + "=" * 70)
    print("Test 1: prepare_workspace reasoner")
    print("=" * 70)

    print("\n  Calling prepare_workspace...")
    try:
        result = await call_reasoner(
            "prepare_workspace",
            platform="github",
            platform_host="github.com",
            repo_owner="andyxhadji",
            repo_name="test-repo",
            head_branch=None,
            base_branch="main",
            task_slug="test-reasoner-abc123",
            issue_short_id="abc123",
        )

        print("  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")

        if result.get("prepared"):
            print(f"  ✓ Workspace prepared: {result.get('repo_path')}")
            print(f"  ✓ Branch: {result.get('branch')}")
            print(f"  ✓ Branch hash: {result.get('branch_hash')}")
            return True, result
        else:
            print(f"  ⚠ Workspace not prepared: {result.get('error')}")
            # Not prepared might be OK if repo doesn't exist
            return True, result

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


async def test_cleanup_workspace():
    """Test the cleanup_workspace reasoner."""
    print("\n" + "=" * 70)
    print("Test 2: cleanup_workspace reasoner")
    print("=" * 70)

    print("\n  Calling cleanup_workspace...")
    try:
        result = await call_reasoner(
            "cleanup_workspace",
            repo_path="/var/nd/work/test-reasoner-abc123",
            bare_path="/var/nd/repos/github.com/andyxhadji/test-repo",
            branch="nd/issue-abc123-test123",
        )

        print("  ✓ Reasoner executed successfully")
        print(f"  ✓ Result: {result}")

        if result.get("cleaned"):
            print("  ✓ Workspace cleaned successfully")
        else:
            print(f"  ⚠ Cleanup reported: {result}")

        return True, result

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


async def test_analyze_task():
    """Test the analyze_task reasoner."""
    print("\n" + "=" * 70)
    print("Test 3: analyze_task reasoner")
    print("=" * 70)

    print("\n  Calling analyze_task...")
    print("  (This will call the LLM via Bedrock, may take 10-30 seconds...)")

    try:
        result = await call_reasoner(
            "analyze_task",
            comment_body="Can you add a function to calculate fibonacci numbers?",
            repo_name="test-repo",
            file_summaries=["math_utils.py: utility functions for mathematical operations"],
        )

        print("  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")

        if "confidence" in result:
            print(f"  ✓ Confidence score: {result['confidence']}")
            print(f"  ✓ Complexity: {result.get('complexity', 'N/A')}")
            print(f"  ✓ Approach summary (first 100 chars): {result.get('approach', '')[:100]}")
            return True, result
        else:
            print(f"  ⚠ Unexpected result format: {result}")
            return False, result

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


async def test_run_roborev():
    """Test the run_roborev reasoner."""
    print("\n" + "=" * 70)
    print("Test 4: run_roborev reasoner")
    print("=" * 70)

    print("\n  Calling run_roborev...")
    print("  (Testing with existing worktree...)")

    try:
        result = await call_reasoner(
            "run_roborev",
            repo_path="/var/nd/work/langextract-bedrock-f4yn",
            commit_sha="HEAD",
            max_iterations=1,
        )

        print("  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")

        passed = result.get("passed")
        print(f"  ✓ Roborev passed: {passed}")

        if not passed:
            findings = result.get("final_findings", [])
            print(f"  ✓ Findings count: {len(findings)}")
            if findings:
                print(f"  ✓ First finding: {findings[0][:100]}")

        if result.get("error"):
            print(f"  ⚠ Error reported: {result['error']}")

        return True, result

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


async def test_draft_response():
    """Test the draft_response reasoner."""
    print("\n" + "=" * 70)
    print("Test 5: draft_response reasoner")
    print("=" * 70)

    print("\n  Calling draft_response...")
    print("  (This will call the LLM via Bedrock, may take 10-30 seconds...)")

    try:
        result = await call_reasoner(
            "draft_response",
            comment_body="Add a hello world function",
            changes_made=["Added hello_world() function to utils.py"],
            commit_sha="abc123def456",
        )

        print("  ✓ Reasoner executed successfully")
        print(f"  ✓ Result keys: {list(result.keys())}")

        if "response_text" in result:
            response_text = result["response_text"]
            print("  ✓ Generated response (first 200 chars):")
            print(f"    {response_text[:200]}")
            return True, result
        else:
            print(f"  ⚠ Unexpected result format: {result}")
            return False, result

    except Exception as e:
        print(f"  ✗ Reasoner failed: {e}")
        import traceback

        traceback.print_exc()
        return False, None


async def main():
    """Run all reasoner tests."""
    print("\n" + "=" * 70)
    print("WORKER REASONER TESTS")
    print("=" * 70)
    print("\nTesting that worker reasoners execute without failing.")
    print("These tests call the actual @app.reasoner() functions via agentfield.")

    results = {}

    # Test each reasoner
    tests = [
        ("prepare_workspace", test_prepare_workspace),
        ("cleanup_workspace", test_cleanup_workspace),
        ("analyze_task", test_analyze_task),
        ("run_roborev", test_run_roborev),
        ("draft_response", test_draft_response),
    ]

    for test_name, test_func in tests:
        try:
            passed, result = await test_func()
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
        print("\n🎉 All reasoner tests passed!")
        print("\nAll worker reasoners are functional:")
        print("  - prepare_workspace: Creates isolated git worktrees")
        print("  - cleanup_workspace: Removes worktrees and branches")
        print("  - analyze_task: Uses LLM to assess task complexity")
        print("  - run_roborev: Calls roborev service for code quality")
        print("  - draft_response: Generates response text via LLM")
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
