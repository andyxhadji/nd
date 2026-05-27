# tests/unit/test_classifier.py
"""Unit tests for comment classifier."""

import pytest
from nd.triage.classifier import CommentClassifier
from nd.schemas import CommentInput


class TestCommentClassifier:
    @pytest.fixture
    def classifier(self):
        return CommentClassifier()

    def test_is_bot_comment(self, classifier):
        assert classifier._is_bot("dependabot[bot]") is True
        assert classifier._is_bot("renovate[bot]") is True
        assert classifier._is_bot("github-actions[bot]") is True
        assert classifier._is_bot("reviewer") is False

    def test_deterministic_actionable_patterns(self, classifier):
        # Explicit requests
        assert classifier._matches_actionable_pattern("Can you fix this?") is True
        assert classifier._matches_actionable_pattern("please update the docs") is True
        assert classifier._matches_actionable_pattern("nit: add a comment here") is True

        # Non-actionable
        assert classifier._matches_actionable_pattern("LGTM") is False
        assert classifier._matches_actionable_pattern("looks good") is False

    def test_deterministic_non_actionable(self, classifier):
        assert classifier._is_non_actionable("LGTM") is True
        assert classifier._is_non_actionable("Looks good!") is True
        assert classifier._is_non_actionable("+1") is True
        assert classifier._is_non_actionable("thanks") is True
        assert classifier._is_non_actionable("Can you fix this?") is False

    def test_classify_bot_comment(self, classifier):
        comment = CommentInput(
            body="I detected a vulnerability",
            author="dependabot[bot]",
            mr_title="Update deps",
            mr_number=1,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is False
        assert result.category == "bot"

    def test_classify_lgtm(self, classifier):
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

    def test_classify_explicit_request(self, classifier):
        comment = CommentInput(
            body="Can you add logging here?",
            author="reviewer",
            mr_title="Add feature",
            mr_number=42,
        )
        result = classifier.classify_deterministic(comment)
        assert result is not None
        assert result.actionable is True
        assert result.category == "request"
