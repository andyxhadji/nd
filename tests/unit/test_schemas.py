# tests/unit/test_schemas.py
"""Unit tests for Pydantic schemas."""

import pytest
from nd.schemas import (
    CommentInput,
    ClassificationResult,
    TaskInput,
    TaskCreationResult,
    AnalysisInput,
    AnalysisResult,
    PollResult,
    ClaimResult,
    TaskDetails,
    ProcessResult,
    SpecDocument,
    ExecutionInput,
    ExecutionResult,
    RoborevInput,
    RoborevResult,
    DraftInput,
    DraftResult,
    ApprovalRequest,
    PostInput,
    FinalizeInput,
)


class TestCommentInput:
    def test_valid_comment(self):
        comment = CommentInput(
            body="Can you fix this?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        assert comment.body == "Can you fix this?"
        assert comment.mr_number == 42


class TestClassificationResult:
    def test_actionable_request(self):
        result = ClassificationResult(
            actionable=True,
            reason="Explicit request with 'fix'",
            category="request",
            confident=True,
        )
        assert result.actionable is True
        assert result.category == "request"

    def test_category_validation(self):
        with pytest.raises(ValueError):
            ClassificationResult(
                actionable=True,
                reason="test",
                category="invalid_category",
                confident=True,
            )


class TestAnalysisResult:
    def test_complexity_range(self):
        result = AnalysisResult(
            complexity=3,
            confidence=85,
            reasoning="Moderate change",
            suggested_approach="Refactor function",
            files_likely_affected=["src/handler.py"],
            confident=True,
        )
        assert result.complexity == 3
        assert result.confidence == 85

    def test_confidence_bounds(self):
        # confidence should be 0-100
        result = AnalysisResult(
            complexity=1,
            confidence=100,
            reasoning="test",
            suggested_approach="test",
            files_likely_affected=[],
            confident=True,
        )
        assert result.confidence == 100
