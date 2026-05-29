"""Injectable mock LLM for AgentField agents in E2E tests.

This module provides a wrapper that can be imported by agent code to replace
app.ai() calls with mock responses.
"""

import os
import sys
from pathlib import Path

# Add mocks directory to path
MOCKS_DIR = Path(__file__).parent
if str(MOCKS_DIR) not in sys.path:
    sys.path.insert(0, str(MOCKS_DIR))

from mock_llm_service import MockLLMService  # noqa: E402


class MockAIWrapper:
    """Wrapper that provides the same interface as app.ai() but returns mocks."""

    def __init__(self):
        self.mock_service = MockLLMService()
        self.call_count = 0

    async def __call__(self, system: str, user: str, **kwargs):
        """Mock implementation of app.ai().

        Args:
            system: System prompt
            user: User prompt
            **kwargs: Additional arguments (ignored in mock)

        Returns:
            dict: Mocked LLM response
        """
        self.call_count += 1

        # Log the call for debugging
        if os.getenv("MOCK_LLM_DEBUG"):
            print(f"[MockLLM] Call #{self.call_count}")
            print(f"[MockLLM] System: {system[:100]}...")
            print(f"[MockLLM] User: {user[:100]}...")

        result = self.mock_service.handle_ai_call(system, user, **kwargs)

        if os.getenv("MOCK_LLM_DEBUG"):
            print(f"[MockLLM] Response: {result}")

        return result


# Global instance
_mock_ai_instance = None


def get_mock_ai():
    """Get or create the global mock AI instance."""
    global _mock_ai_instance
    if _mock_ai_instance is None:
        _mock_ai_instance = MockAIWrapper()
    return _mock_ai_instance


def patch_agentfield_ai(app):
    """Patch an AgentField app instance to use mock AI.

    Args:
        app: AgentField app instance

    Usage in agent code:
        if os.getenv("USE_MOCK_LLM"):
            from tests.e2e.mocks.mock_llm_injector import patch_agentfield_ai
            patch_agentfield_ai(app)
    """
    original_ai = app.ai
    mock_ai = get_mock_ai()

    # Replace app.ai with mock
    app.ai = mock_ai

    print("✓ AgentField app.ai() patched with MockLLM")

    return original_ai  # Return original in case caller wants to restore
