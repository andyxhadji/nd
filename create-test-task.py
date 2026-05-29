#!/usr/bin/env python3
"""
Create a test task for the worker to claim and process.

This creates a kata task that will trigger the full worker workflow including
roborev integration.
"""

import asyncio
import sys

from agentfield import Agent, AIConfig


async def main():
    print("=" * 70)
    print("CREATE TEST TASK FOR WORKER")
    print("=" * 70)

    # Create agent to call triage
    trigger = Agent(
        node_id="test-task-creator",
        version="1.0.0",
        agentfield_server="http://agentfield:8080",
        ai_config=AIConfig(
            model="bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/mj2ayeqbysnr"
        ),
    )

    print("\n1. Creating test task via triage agent...")
    print("   This will create a simple coding task")

    try:
        # Call triage to create a task
        result = await trigger.call(
            "nd-triage.create_task",
            payload={
                "comment_body": "Add a simple hello_world function that returns 'Hello, World!'",
                "comment_dedupe_key": "test-task-roborev-e2e-001",
                "platform": "github",
                "platform_host": "github.com",
                "repo_owner": "andyxhadji",
                "repo_name": "test-repo",
                "base_branch": "main",
                "context_url": "https://github.com/andyxhadji/test-repo/issues/1",
                "comment_author": "test-user",
            },
        )

        print(f"\n   Result: {result}")

        if result.get("created"):
            print("\n✅ Task created successfully!")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   Idempotency key: {result.get('idempotency_key')}")
            print("\n2. Now trigger worker to claim this task:")
            print("   python create-test-task.py --claim")
            return 0
        else:
            print(f"\n⚠ Task not created: {result.get('error')}")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


async def claim_task():
    """Trigger worker to claim and process a task."""
    print("=" * 70)
    print("TRIGGER WORKER TO CLAIM TASK")
    print("=" * 70)

    trigger = Agent(
        node_id="test-worker-trigger",
        version="1.0.0",
        agentfield_server="http://agentfield:8080",
        ai_config=AIConfig(
            model="bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/mj2ayeqbysnr"
        ),
    )

    print("\n1. Triggering worker to claim and process task...")
    print("   Target: nd-worker.claim_task")

    try:
        result = await trigger.call("nd-worker.claim_task", payload=None)

        print(f"\n   Result: {result}")

        if result.get("claimed"):
            print(f"\n✅ Task claimed: {result['task_id']}")
            print(f"   Project: {result.get('project')}")
            print("\n2. Worker is now processing the task...")
            print("   This includes:")
            print("   - ✓ Workspace preparation (git worktree)")
            print("   - ✓ Task analysis (LLM via Bedrock)")
            print("   - ✓ Code execution (Claude Code)")
            print("   - ✓ Roborev validation ← NEW!")
            print("   - ✓ Draft response")
            print("   - ⏸ Pause for approval")
            print("\n📊 Monitor progress:")
            print("   - AgentField: http://localhost:8081")
            print("   - Dashboard: http://localhost:3000")
            print("   - Worker logs: docker logs hyper-furniture-worker-1-1 -f")
            print("\n✅ Successfully triggered full worker workflow with roborev!")
            return 0
        else:
            print(f"\n⚠ No task claimed: {result.get('error', 'No unowned tasks available')}")
            print("   Create a task first: python create-test-task.py")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--claim":
        exit_code = asyncio.run(claim_task())
    else:
        exit_code = asyncio.run(main())
    sys.exit(exit_code)
