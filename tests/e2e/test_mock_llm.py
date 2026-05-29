"""Tests for Mock LLM service functionality."""

from tests.e2e.mocks.mock_llm_service import MockLLMService


class TestMockLLMClassification:
    """Test mock LLM comment classification."""

    def test_classifies_lgtm_as_not_actionable(self):
        """Test LGTM is classified as non-actionable."""
        result = MockLLMService.classify_comment("LGTM")
        assert result["actionable"] is False
        assert result["category"] == "acknowledgment"
        assert result["confident"] is True

    def test_classifies_question_as_actionable(self):
        """Test questions are classified as actionable."""
        result = MockLLMService.classify_comment("Can you add tests?")
        assert result["actionable"] is True
        assert result["category"] == "question"

    def test_classifies_request_as_actionable(self):
        """Test requests are classified as actionable."""
        result = MockLLMService.classify_comment("Please fix the typo in line 42")
        assert result["actionable"] is True
        assert result["category"] == "request"

    def test_classifies_bot_comment_as_not_actionable(self):
        """Test bot comments are classified as non-actionable."""
        result = MockLLMService.classify_comment("Build passed", author="github-actions[bot]")
        assert result["actionable"] is False
        assert result["category"] == "bot"

    def test_classifies_review_marker_as_actionable(self):
        """Test review markers are classified as actionable."""
        result = MockLLMService.classify_comment("nit: consider using a list comprehension")
        assert result["actionable"] is True
        assert result["category"] == "review"


class TestMockLLMComplexity:
    """Test mock LLM complexity analysis."""

    def test_simple_task_low_complexity(self):
        """Test simple tasks get low complexity scores."""
        result = MockLLMService.analyze_complexity("Fix typo in comment")
        assert result["complexity"] <= 30
        assert "simple" in result["reasoning"].lower()

    def test_complex_task_high_complexity(self):
        """Test complex tasks get high complexity scores."""
        result = MockLLMService.analyze_complexity(
            "Refactor the authentication system to use JWT tokens "
            "and implement refresh token rotation with proper expiry handling"
        )
        assert result["complexity"] >= 70
        assert (
            "complex" in result["reasoning"].lower() or "significant" in result["reasoning"].lower()
        )

    def test_medium_task_moderate_complexity(self):
        """Test medium tasks get moderate complexity scores."""
        result = MockLLMService.analyze_complexity("Add logging to the request handler")
        assert 30 <= result["complexity"] <= 70


class TestMockLLMPlanning:
    """Test mock LLM planning functionality."""

    def test_planning_for_test_task(self):
        """Test planning generates appropriate steps for test tasks."""
        result = MockLLMService.plan_changes("Add tests for the user service")
        assert "plan" in result
        assert "test" in result["plan"].lower()
        assert isinstance(result["estimated_files"], int)

    def test_planning_for_bug_fix(self):
        """Test planning generates appropriate steps for bug fixes."""
        result = MockLLMService.plan_changes("Fix bug in login validation")
        assert "plan" in result
        assert any(word in result["plan"].lower() for word in ["fix", "bug", "reproduce"])

    def test_planning_for_refactor(self):
        """Test planning generates appropriate steps for refactoring."""
        result = MockLLMService.plan_changes("Refactor the database layer")
        assert "plan" in result
        assert "refactor" in result["plan"].lower()


class TestMockLLMResponse:
    """Test mock LLM response drafting."""

    def test_drafts_success_response(self):
        """Test drafting a successful completion response."""
        result = MockLLMService.draft_response("Add logging", "success", "abc1234")
        assert "response" in result
        assert "logging" in result["response"].lower()
        assert "abc123" in result["response"]  # Shortened commit SHA

    def test_drafts_needs_review_response(self):
        """Test drafting a response that needs review."""
        result = MockLLMService.draft_response("Complex refactoring", "needs_review")
        assert "response" in result
        assert "confirm" in result["response"].lower() or "review" in result["response"].lower()


class TestMockLLMHandleAICall:
    """Test main dispatcher for app.ai() calls."""

    def test_handles_classification_call(self):
        """Test dispatching to classification."""
        result = MockLLMService.handle_ai_call(
            system="You classify MR comments as actionable or not",
            user="Body: LGTM\nAuthor: reviewer",
        )
        assert "actionable" in result
        assert result["actionable"] is False

    def test_handles_complexity_call(self):
        """Test dispatching to complexity analysis."""
        result = MockLLMService.handle_ai_call(
            system="Estimate the complexity of this task", user="Add a new API endpoint"
        )
        assert "complexity" in result
        assert isinstance(result["complexity"], int)

    def test_handles_planning_call(self):
        """Test dispatching to planning."""
        result = MockLLMService.handle_ai_call(
            system="Create an implementation plan", user="Implement user authentication"
        )
        assert "plan" in result

    def test_handles_unknown_call_gracefully(self):
        """Test fallback for unknown system prompts."""
        result = MockLLMService.handle_ai_call(system="Some unknown prompt type", user="Test input")
        # Should return something without crashing
        assert isinstance(result, dict)
