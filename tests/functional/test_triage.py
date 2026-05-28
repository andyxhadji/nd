"""Functional tests for triage agent."""

import pytest

from nd.schemas import CommentInput
from nd.triage.classifier import CommentClassifier


@pytest.mark.functional
class TestTriageClassification:
    def test_classify_actionable_request(self):
        """Test classification of explicit request."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="Can you add logging to this function?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "request"

    def test_classify_non_actionable_lgtm(self):
        """Test classification of LGTM."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="LGTM",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "acknowledgment"

    def test_classify_bot_comment(self):
        """Test classification of bot comment."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="I found a security issue",
            author="dependabot[bot]",
            mr_title="Update deps",
            mr_number=1,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "bot"

    def test_classify_question(self):
        """Test classification of question."""
        classifier = CommentClassifier()
        comment = CommentInput(
            body="Why did you choose this approach?",
            author="reviewer",
            mr_title="Refactor",
            mr_number=10,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "question"
