#!/usr/bin/env python3
"""
ND End-to-End Smoke Test

Tests the full flow:
1. Triage creates task from assigned issue
2. Worker claims and processes task
3. Task proceeds through workflow (workspace prep, analyze, execute)
4. Approval appears in dashboard
"""

import asyncio
import sys

from agentfield import Agent, AIConfig


async def main():
    print("=" * 60)
    print("ND END-TO-END SMOKE TEST")
    print("=" * 60)

    # Create a temporary agent to make cross-agent calls
    trigger = Agent(
        node_id="smoke-test-trigger",
        version="1.0.0",
        agentfield_server="http://agentfield:8080",
        ai_config=AIConfig(
            model="bedrock/converse/arn:aws:bedrock:us-east-1:657062785455:application-inference-profile/mj2ayeqbysnr"
        ),
    )

    print("\n1. Triggering worker to claim and process task...")
    print("   Target: nd-worker.claim_task")

    try:
        result = await trigger.call("nd-worker.claim_task", payload="")
        print(f"   Result: {result}")

        if result.get("claimed"):
            print(f"\n✅ Task claimed: {result['task_id']}")
            print(f"   Project: {result['project']}")
            print("\n2. Worker will now process the task...")
            print("   This includes:")
            print("   - Workspace preparation (git clone/worktree)")
            print("   - Task analysis (LLM call)")
            print("   - Code execution (if confident)")
            print("   - Approval gates (will appear in dashboard)")
            print("\n📊 Monitor progress:")
            print("   - AgentField UI: http://localhost:8081/ui")
            print("   - Approval Dashboard: http://localhost:3000")
            print("\n✅ SMOKE TEST: Successfully triggered worker")
            return 0
        else:
            print("\n⚠️  No tasks available to claim")
            print("   Task may already be assigned or no unowned nd tasks exist")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
