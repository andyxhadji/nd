#!/usr/bin/env python3
"""Test that roborev service has working claude agent integration."""
import asyncio
import sys


async def test_roborev_agent():
    """Test that roborev can detect and use claude agent in container."""
    print("Testing roborev service with claude agent integration...")
    print("=" * 60)

    # Test 1: Check claude agent is detected
    print("\n1. Checking if roborev can detect claude agent...")
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "hyper-furniture-roborev-1",
        "roborev",
        "check-agents",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if b"claude-code" in stdout and b"OK" in stdout:
        print("   ✓ Claude agent detected and passed health check")
    else:
        print("   ✗ Claude agent not detected or failed")
        print(f"     Output: {stdout.decode()}")
        return False

    # Test 2: Worker can call roborev via docker exec
    print("\n2. Testing worker → roborev communication...")
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "hyper-furniture-worker-1-1",
        "docker",
        "exec",
        "-w",
        "/var/nd",
        "hyper-furniture-roborev-1",
        "roborev",
        "check-agents",
        "--agent",
        "claude-code",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        print("   ✓ Worker can successfully call roborev service")
    else:
        print("   ✗ Worker failed to call roborev service")
        print(f"     Error: {stderr.decode()}")
        return False

    # Test 3: Roborev has access to workspace
    print("\n3. Verifying roborev can access workspace directories...")
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "hyper-furniture-roborev-1",
        "ls",
        "-la",
        "/var/nd/work",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0 and len(stdout) > 0:
        print("   ✓ Roborev has access to workspace directories")
        # Show workspace contents
        print(f"     Workspace: {stdout.decode().strip().split()[2:4]}")
    else:
        print("   ✗ Roborev cannot access workspace")
        return False

    # Test 4: Check AWS credentials are available
    print("\n4. Checking AWS credentials for Bedrock access...")
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "hyper-furniture-roborev-1",
        "env",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    env_vars = stdout.decode()

    if "AWS_ACCESS_KEY_ID" in env_vars and "AWS_SECRET_ACCESS_KEY" in env_vars:
        print("   ✓ AWS credentials available for Bedrock")
    else:
        print("   ⚠ AWS credentials not found (claude may use API key instead)")

    print("\n" + "=" * 60)
    print("All tests passed! Roborev service is fully functional.")
    print("\nNext steps:")
    print("  - Run worker tasks to test end-to-end roborev integration")
    print("  - Monitor roborev output when worker calls run_roborev reasoner")
    print("  - Verify code quality checks pass with claude agent")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_roborev_agent())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
