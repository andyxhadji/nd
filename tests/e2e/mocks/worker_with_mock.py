"""Wrapper to run worker agent with mock LLM in E2E tests.

Usage:
    docker compose run -e USE_MOCK_LLM=1 worker python tests/e2e/mocks/worker_with_mock.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, "/app")

# Import agent factory
from nd.config import config
from nd.worker.agent import create_worker_agent

# Create agent instance
app = create_worker_agent()

# Patch with mock LLM if requested
if os.getenv("USE_MOCK_LLM"):
    from mock_llm_injector import patch_agentfield_ai

    patch_agentfield_ai(app)
    print("🧪 Worker agent running with Mock LLM")
else:
    print("⚠️  USE_MOCK_LLM not set, using real LLM (will require API key)")

# Run the agent
if __name__ == "__main__":
    if config.agent_port:
        app.run(host="0.0.0.0", port=config.agent_port, auto_port=False)
    else:
        app.run(auto_port=True)
